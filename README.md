# slurmacc
Tools to add extra information from LDAP to the user info in SLURM sreport overviews.

# About

The slurmacc.py script combines data from SLURM sreport and the SLURM database in order to generate readable reports on 
the usage of the cluster.

Usage data is read from sreport, while user data is read from the database. These two are aggregated in order to obtain
information about how much different faculties and departments are utilising the cluster. 

The script is able to report the usage in CPU time (in either hours, minutes, seconds, or as a percentage of the total)
or the number of jobs started by each account (although sreport take very long to actually gather this data). Specific 
periods of time can be requested, as well as specific accounts.

The script requires the credentials for a database user, as well as information about the database host machine and the 
specific database. These are provided in a config.ini file, which the program can create if it does not exist. The file 
then needs to be modified to add the user credentials.

The output data can be grouped by any combination of the faculties, the departments and the users. The output is by 
default ordered by the faculty, department ids and the username, but it can be sorted by the selected metric instead. 
The output is by default printed on screen, but a csv of it can be generated.

[//]: # (The slurmacc file is used to create a data base of a persons UID, the field he/she works in and his/her full name, using Lightweight Directory Access Protocol &#40;LDAP&#41;, and then reports the amount of time spend by the user. )
[//]: # (slurmacc.py also adds missing users from LDAP that are in sReport to the database. All fields that are unknown can be filled in manually, but will get updated if the fields are known in LDAP and are different.)
[//]: # (The data from sreport that yields the amount of wallclock time spend on the cores of the Peregrine cluster is paired with the UID and then distributed over their fields.)
[//]: # (For example if someone has an UID of p123456 and is in the departments Artificial Intelligence,XYZ and Biomedical Engineering,WXY and sReport has a value of 100 hours consumed on the cluster,)
[//]: # (then the fields Artificial Intelligence,XYZ and Biomedical Engineering,WXY both get accounted for 50 hours.)
[//]: # (If this is done for every user, all time spend for every department is added up such that it is clear which department has used the cluster for a certain time.)
[//]: # (At last it is also possible to request the amount of time used by the faculty codes. This means that the time of Artificial Intelligence,XYZ and Computing Science,XYZ are added to the faculty code XYZ.)
[//]: # (This file prioritises the data from LDAP, but if information is missing, then it will use the fields that are added manually or at last name them to unknown. If a person gets removed from LDAP, the person is put in another file with the date of removement. )
[//]: # (Hence, this file is an up-to-date datebase of all users in LDAP and is able to report the time spend on a cluster for the user, department, or faculty code.)

# How to use

To use the script, several python packages have to be installed. They are pip frozen in the file `requirements.txt`. The
script has been created and tested with Python version 3.10.8. 

The basic usage is summarized by the help message of the script: 
```
Usage: slurmacc.py [options]

Options:
  -h, --help            show this help message and exit
  -b, --debug           Shows extra information about the progression of the
                        program
  -g CONFIG_FILE, --config=CONFIG_FILE
                        Path to the config file used by the script. Defaults
                        to 'config.ini'
  -s START_DATE, --start_date=START_DATE
                        Only include accounting records from this date on.
                        Defaults to one year ago. Format: yyyy-mm-dd.
  -e END_DATE, --end_date=END_DATE
                        Only include accounting records for up to, and not
                        including this date. Defaults to today. Format yyyy-
                        mm-dd.
  -a ACCOUNTS, --accounts=ACCOUNTS
                        Query data only for the selected accounts. To add
                        multiple accounts,pass them separated by , with no
                        spaces. Defaults to querying for all accounts
  -c, --cpu_time        Report on used cpu time (units defined by -t).
                        Mutually exclusive with -j. Default behaviour if no
                        metric argument is provided
  -j, --jobs            Report on number of jobs run. Mutually exclusive with
                        -c
  -t TIME_UNIT, --time=TIME_UNIT
                        Output time unit for -c. Must be one of (h, m, s, p),
                        where p is %.Defaults to minutes.
  -n, --name            Use the full name instead of the username for user
                        accounting information
  -u, --user            Present accounting information for individual users
  -d, --department      Present accounting information for departments
  -f, --faculty         Present accounting information faculties
  -o, --sort            Sort table on on cpu time instead of account, faculty
                        department or user
  -v, --view            Prints the results to the screen in human readable
                        format. Default behaviour if no output argument is
                        provided
  -x, --csv             Output results in comma separated value format, in a
                        file named usage_<metric>_<start-date>-<end-date>
```

Running the script for the first time creates a configuration file that needs to be modified with the correct 
credentials.

The default behaviour for the program is to return a breakdown of the CPU time in minutes for the past year.

The following command prints a breakdown of the CPU time for the month of october 2023 for each user, in seconds.

```commandline
slurmacc.py -s 2023-10-1 -e 2023-11-01 -c -t s
```

The following command prints a sorted breakdown of the CPU time, in percentages, for the period Jun-Aug 2022 for each faculty,
and only from the 'users' account, while also writing the data to a csv file.

```commandline
slurmacc.py -s 2022-6-1 -e 2022-09-01 -c -t p -f -o -v -x 
```

The following command write a csv file of the CPU time, in hours, for the past year, broken down by faculty,
department and users.

```commandline
slurmacc.py -t h -f -d -u -x 
```
