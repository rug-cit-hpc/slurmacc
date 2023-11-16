#!/usr/bin/env python3

import os
import sys
import logging
import subprocess
from configparser import ConfigParser
from optparse import OptionParser
from datetime import date
from io import StringIO

import pandas as pd
import sqlalchemy


def setup_logging():
    logging.basicConfig(
        format="%(levelname)s %(asctime)s %(message)s", datefmt="%H:%M:%S",
        level=logging.ERROR,
        handlers=[logging.StreamHandler(sys.stderr)]
    )


def parse_args():
    today = date.today()

    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)

    parser.add_option("-b", "--debug", dest="debug", default=False, action="store_true",
                      help="Shows extra information about the progression of the program")

    parser.add_option("-g", "--config", dest="config_file", default="config.ini",
                      help="Path to the config file used by the script. Defaults to 'config.ini'")

    parser.add_option("-s", "--start_date", dest="start_date",
                      default=str(date(today.year - 1, today.month, today.day)),
                      help="Only include accounting records from this date on. " +
                           "Defaults to one year ago. Format: yyyy-mm-dd.")

    parser.add_option("-e", "--end_date", dest="end_date", default=str(today),
                      help="Only include accounting records for up to, " +
                           "and not including this date. Defaults to today. Format yyyy-mm-dd.")

    parser.add_option("-a", "--accounts", dest="accounts", default="",
                      help="Query data only for the selected accounts. To add multiple accounts,"
                           "pass them separated by , with no spaces. Defaults to querying for "
                           "all accounts")

    parser.add_option("-c", "--cpu_time", dest="cpu_time", default=False, action="store_true",
                      help="Report on used cpu time (units defined by -t). "
                           "Mutually exclusive with -j. " +
                           "Default behaviour if no metric argument is provided")

    parser.add_option("-j", "--jobs", dest="jobs", default=False, action="store_true",
                      help="Report on number of jobs run. Mutually exclusive with -c or -m")

    time_units = ["h", "m", "s", "p"]

    parser.add_option("-t", "--time", dest="time_unit", default='m',
                      help=f"Output time unit for -c. Must be one of ({', '.join(time_units)}), "
                           f"where p is %.Defaults to minutes.")

    parser.add_option("-m", "--monthly", dest="monthly", default=False, action="store_true",
                      help="Present accounting as a series of columns, each representing a different "
                           "month. Mutually exclusive with -j. Creates a report containing each full "
                           "month starting with the start date month, up to and NOT including the end "
                           "date month")

    parser.add_option("-u", "--user", dest="user", default=False, action="store_true",
                      help="Present accounting information for individual users")

    parser.add_option("-d", "--department", dest="department", default=False, action="store_true",
                      help="Present accounting information for departments")

    parser.add_option("-f", "--faculty", dest="faculty", default=False, action="store_true",
                      help="Present accounting information faculties")

    parser.add_option("-o", "--sort", dest="sort", default=False, action="store_true",
                      help="Sort table on on cpu time instead of account, faculty department or user")

    parser.add_option("-v", "--view", dest="view", default=False, action="store_true",
                      help="Prints the results to the screen in human readable format. Default "
                           "behaviour if no output argument is provided")

    parser.add_option("-x", "--csv", dest="csv", default=False, action="store_true",
                      help="Output results in comma separated value format, in a file named "
                           "usage_<metric>_<start-date>-<end-date>")

    # TODO: maybe add flag for generating for all users

    options, args = parser.parse_args()

    if options.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logging.debug("Checking arguments.")

    if os.path.isdir(options.config_file):
        logging.error("Config path points to a directory")
        exit(1)

    try:
        options.start_date = pd.Timestamp(options.start_date)
        options.end_date = pd.Timestamp(options.end_date)
    except:
        logging.error("Wrong date specified for -s or -e, use the format yyyy-mm-dd")
        exit(1)

    if options.start_date > options.end_date:
        logging.error("start date cannot be after end date")
        exit(1)

    if options.cpu_time and options.jobs:
        logging.error("Options -c and -j are mutually exclusive")
        exit(1)

    if not any([options.cpu_time, options.jobs]):
        logging.debug("No metric argument provided. Using CPU time")
        options.cpu_time = True

    if options.time_unit not in time_units:
        logging.error(f"Invalid time unit selected: '{options.time_unit}'. Must be one of {', '.join(time_units)}")
        exit(1)

    if not any([options.view, options.csv]):
        logging.debug("No output argument provided. Printing to screen")
        options.view = True

    if options.jobs and options.monthly:
        logging.error("Options -j and -m are mutually exclusive")
        exit(1)

    logging.debug("Finished checking arguments")
    return options


def parse_configs(options):
    logging.debug(f"Reading config file {options.config_file}")
    cfg = ConfigParser()

    # Dictionary containing default values, used for creating new config files and checking all variables are present
    defaults = {
        'database': {
            'username': 'placeholder',
            'password': 'placeholder',
            'host': 'database1',
            'database': 'hb_useradmin'
        }
    }

    # If the config file does not exist, create a skeleton for it and exit
    if not os.path.exists(options.config_file):
        logging.debug("Config file does not exist. Creating it with default values")

        for section, variables in defaults.items():
            cfg.add_section(section)
            for variable, value in variables.items():
                cfg.set(section, variable, value)

        with open(options.config_file, "x") as cfg_file:
            cfg.write(cfg_file)

        logging.error(f"Config file has been created at '{options.config_file}'.\n"
                      f"Provide database (user) credentials in it and run the script again")
        exit(1)

    # If it does exist, read it and check it contains all required values
    logging.debug("Checking that config file contains all required values")
    with open(options.config_file, "r") as cfg_file:
        cfg.read_file(open(options.config_file))

    all_present = all(
        cfg.has_section(section) and  # check if section exists
        all((cfg.has_option(section, option) for option in variables))  # check if section contains all vars
        for section, variables in defaults.items()
    )

    if not all_present:
        logging.error(f"Config file does not contain the required data.\n")
        exit(1)

    logging.debug("Finished reading config file")
    return cfg


def get_usage_data(options):
    logging.debug("Gathering usage data with sreport")

    command = ['sreport', "-P"]

    if options.cpu_time:
        command.extend(["cluster", "AccountUtilizationByUser",
                        "-t" + str(options.time_unit), "format=Login,Account,Used"])
    elif options.jobs:
        command.extend(["job", "SizesByAccount", "PrintJobCount", "FlatView"])

    command.extend(["start=" + options.start_date.strftime("%Y-%m-%d"), "end=" + options.end_date.strftime("%Y-%m-%d")])
    if options.accounts != "":
        command.append("Accounts=" + options.accounts)

    try:
        logging.debug(f"Starting subprocess with command {' '.join(command)}")

        sreport = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
        output, err = sreport.communicate()

        logging.debug(f"Subprocess finished")
    except:
        logging.error(f"Running sreport failed. Command used: '{' '.join(command)}'")
        exit(1)

    try:
        logging.debug(f"Interpreting output as csv")

        usage_data = pd.read_csv(StringIO(output), delimiter='|', skiprows=4)

        if options.cpu_time:
            usage_data = usage_data[pd.notnull(usage_data["Login"])]
    except:
        logging.error(f"Failed to read sreport output as csv.")
        logging.debug(f"The output was:\n{output}")
        exit(1)

    if usage_data.empty:
        logging.error(f"sreport returned no entry for the given period. {options.start_date.strftime('%Y-%m-%d')} "
                      f"to {options.end_date.strftime('%Y-%m-%d')}")
        exit(1)

    return usage_data


def get_database_data(usage, options, configs):
    logging.debug("Querying the database for user data")
    db_conf = configs["database"]

    try:
        engine = sqlalchemy.create_engine(
            f"mysql+mysqlconnector://"
            f"{db_conf['username']}:{db_conf['password']}"
            f"@{db_conf['host']}/{db_conf['database']}"
        )
    except:
        logging.error("Failed to connect to database")
        exit(1)

    username_list = (f"'{username}'" for username in usage["Login"])
    start_date = f"'{options.start_date.strftime('%Y-%m-%d')}'"
    end_date = f"'{options.end_date.strftime('%Y-%m-%d')}'"

    # The script uses a hardcoded query in order to
    # not duplicate code from / be dependent on "rug-cit-hpc/hb-user-management"
    query = f"""
            SELECT
                users.username AS Login,
                users.name AS Name,
                departments.name AS Department,
                faculties.name AS Faculty,
                affiliations.start_date AS StartDate
            FROM users
            LEFT JOIN affiliations
                ON users.id = affiliations.user_id
            LEFT JOIN departments
                ON affiliations.department_id = departments.id
            LEFT JOIN faculties
                ON departments.faculty_id = faculties.id
            WHERE users.username IN ({', '.join(username_list)})
              AND users.start_date < {end_date}
              AND (users.end_date >= {start_date} OR users.end_date IS NULL)
              AND affiliations.start_date < {end_date}
              AND (affiliations.end_date >= {start_date} OR affiliations.end_date IS NULL)
              AND departments.date_added < {end_date}
              AND (departments.date_removed >= {start_date} OR departments.date_removed IS NULL)
              AND faculties.date_added < {end_date}
              AND (faculties.date_removed >= {start_date} OR faculties.date_removed IS NULL)
            ;"""

    try:
        user_data = pd.read_sql(query, engine, parse_dates=["StartDate"])
    except:
        logging.error("Failed to query the database with pandas and sqlalchemy")
        exit(1)

    logging.debug("Using only the latest affiliation for each user")

    user_data = user_data.sort_values(by='StartDate', ascending=False)
    user_data = user_data.drop_duplicates(subset=['Login'])
    user_data = user_data.drop(["StartDate"], axis=1)

    if user_data["Department"].isnull().any():
        logging.error("Some users from the database have no department affiliation. "
                      "Marking them as 'Unknown Department'")
        user_data["Department"] = user_data["Department"].fillna("Unknown Department")

    if user_data["Faculty"].isnull().any():
        logging.error("Some users from the database have no faculty affiliation. "
                      "Marking them as 'Unknown Faculty'")
        user_data["Faculty"] = user_data["Faculty"].fillna("Unknown Faculty")

    return user_data


def combine(usage, user, options):
    logging.debug("Combining the usage data with the user data.")
    combined = usage.set_index("Login").join(user.set_index("Login"))

    logging.debug("Keeping only the requested identifiers")
    data = combined.reset_index()

    data["User"] = data["Login"]
    data = data.drop(["Login"], axis=1)

    logging.debug("Grouping data")
    if options.faculty or options.department:
        # If any flags apart from -u are set, group data before returning
        grouping = ["Account"]

        if options.faculty:
            grouping.append("Faculty")

        if options.department:
            grouping.append("Department")

        if options.user:
            grouping.extend(["User", "Name"])
        else:
            data = data.drop(["Name"], axis=1)

        data = data.groupby(grouping)["Used"].sum()

        if options.sort:
            logging.debug("Sorting entries")
            data = data.sort_values(ascending=False)
    elif options.monthly:
        grouping = ["Account", "User", "Name", "Faculty", "Department"]
        data = data.groupby(grouping)["Used"].sum()
    else:
        # Otherwise return the table as is
        data = data.set_index("User")

        if options.sort:
            logging.debug("Sorting entries")
            data = data.sort_values(by="Used", ascending=False)

    return data


def output_data(data, options):
    # Print to screen
    if options.view:
        logging.debug("Printing data on screen")
        print(data.to_string())

    # Write to csv
    if options.csv:
        # Base name
        csv_name = "usage"

        # Metric
        if options.cpu_time:
            csv_name += "_cpu_" + options.time_unit
        elif options.jobs:
            csv_name += "_jobs"

        # Monthly
        if options.monthly:
            csv_name += "_monthly"

        # Time period
        csv_name += "_" + options.start_date.strftime("%Y-%m-%d") + "_" + options.end_date.strftime("%Y-%m-%d") + ".csv"

        logging.debug(f"Writing data to csv file {csv_name}")

        data.to_csv(csv_name)


def process_jobs(options, configs):
    logging.debug("Processing job request")

    usage_data = get_usage_data(options)
    return usage_data


def process_single(options, configs):
    logging.debug("Processing single period request")

    # Read sreport data
    usage_data = get_usage_data(options)

    # Gather database data
    user_data = get_database_data(usage_data, options, configs)

    # Combine the two and return
    combined_data = combine(usage_data, user_data, options)
    return combined_data


def process_multiple(options, configs):
    logging.debug("Processing monthly report request")

    start_month = options.start_date.to_period(freq='M')
    end_month = options.end_date.to_period(freq='M')

    current_month = start_month
    current_start = current_month.start_time
    current_end = (current_month + 1).start_time

    results = []

    while current_end <= end_month.start_time:
        options.start_date = current_start
        options.end_date = current_end

        temp_res = process_single(options, configs)
        temp_res = pd.DataFrame({current_month.strftime("%Y-%m"): temp_res}, index=temp_res.index)
        results.append(temp_res)

        current_month += 1
        current_start = current_month.start_time
        current_end = (current_month + 1).start_time

    logging.debug("Gathered data for the entire period. Merging in one table")

    res = results.pop(0)
    for ser in results:
        res = res.join(ser, how='outer')

    res = res.fillna(0).astype(int)
    res["Total"] = res.sum(axis=1, numeric_only=True)

    if options.sort:
        logging.debug("Sorting merged table")
        res = res.sort_values(by="Total", ascending=False)

    return res


def main():
    setup_logging()
    options = parse_args()
    configs = parse_configs(options)

    # Process the result accordingly
    if options.jobs:
        result = process_jobs(options, configs)
    elif options.monthly:
        result = process_multiple(options, configs)
    else:
        result = process_single(options, configs)

    # Output the data
    output_data(result, options)


if __name__ == '__main__':
    main()
