# instagram_monitor

instagram_monitor is a Python script which allows for real-time monitoring of Instagram users activity. 

## Features

- Real-time monitoring of different activities performed by monitored Instagram users:
   - new posts & stories
   - changed followings, followers, bio
- Email notifications for different events (new posts & stories, changed followings, followers, bio, errors)
- Saving all user activities with timestamps to the CSV file
- Support for both public and private profiles
- Two modes of operation: with or without logged in Instagram account
- Different mechanisms to prevent captcha and detection of automated tools
- Possibility to control the running copy of the script via signals

<p align="center">
   <img src="./assets/instagram_monitor.png" alt="instagram_monitor_screenshot" width="70%"/>
</p>

## Change Log

Release notes can be found [here](RELEASE_NOTES.md)

## Disclaimer

I'm not a dev, project done as a hobby. Code is ugly and as-is, but it works (at least for me) ;-)

## Requirements

The script requires Python 3.x.

It uses [instaloader](https://github.com/instaloader/instaloader) library, also requires requests, python-dateutil and pytz.

It has been tested succesfully on Linux (Raspberry Pi Bullseye & Bookworm based on Debian) and Mac OS (Ventura & Sonoma). 

Should work on any other Linux OS and Windows with Python.

## Installation

Install the required Python packages:

```sh
python3 -m pip install requests python-dateutil pytz instaloader
```

Or from requirements.txt:

```sh
pip3 install -r requirements.txt
```

Copy the *[instagram_monitor.py](instagram_monitor.py)* file to the desired location. 

You might want to add executable rights if on Linux or MacOS:

```sh
chmod a+x instagram_monitor.py
```

## Configuration

Edit the  *[instagram_monitor.py](instagram_monitor.py)* file and change any desired configuration variables in the marked **CONFIGURATION SECTION** (all parameters have detailed description in the comments).

### Mode 1 without logged in Instagram account

First mode of tool operation assumes you do not use your Instagram account to monitor other users. 

This way you can still monitor basic activities of the user like new posts, stories, changed bio and also changed number of followers & followings, but without information what followers/followings have been added or removed.

This mode is easy to use, does not require any preparation and is resistant to Instagram's anticaptcha and automated tool detection mechanisms.

### Mode 2 with logged in Instagram account

Second mode of tool operation assumes you use Instagram account to perfom session logging in the tool and to monitor other users. 

This way you can also get information about added/removed followers and followings (in previous version of the tool it also allowed to get list of comments and likes for new posts, however it has been blocked recently).

I suggest to create a new account for the usage with the tool as there is small risk the account might get banned. However I use few accounts since more than a year with this tool and all the accounts are still active, however from time to time Instagram might present some warnings about detected suspicious activity. 

You can define the username and password directly in the .py file (or via **-u** and **-p** parameters), however it means that logging procedure is performed every time the tool is executed. It is highly recommended to log in once and save the session information using **instaloader** tool. 

Once you installed the instaloader pip package, the needed binary should be available and you can log in as in the example below (user *misiek_to_ja_mon*):

```sh
instaloader -l misiek_to_ja_mon
```

It will ask for your password and save the session. However this method presents an issue that after some time Instagram will most likely report detection of an automated tool, especially in case of frequent changes of followers/followings of the monitored users.

To overcome this it is suggested to use the most recommended way - using the session cookie from your web browser. 

Use Firefox web browser, log in to the Instagram account which you want to use to monitor other users and then use [instaloader_import_firefox_session.py](instaloader_import_firefox_session.py) to import the session from Firefox's *cookies.sqlite* to instaloader (you might have to adjust the path of your Firefox profile in this script). Then use the above instaloader command again.

This method has an advantage that if you do some activities with this account in your Firefox browser every few days (like scrolling through feed, liking some posts) it will count as "good" activity which will increase reputation of tool's actions. Sometimes you might still see some warnings in your Firefox web browser where you need to solve some captcha, but it should not be too often.

### Timezone

You can specify your local time zone so the tool converts post's comments timestamps to your time:

```
LOCAL_TIMEZONE='Europe/Warsaw'
```

### SMTP settings

If you want to use email notifications functionality you need to change the SMTP settings (host, port, user, password, sender, recipient). If you leave the default settings then no notifications will be sent.

### Other settings

All other variables can be left at their defaults, but feel free to experiment with it.

## Getting started

### List of supported parameters

To get the list of all supported parameters:

```sh
./instagram_monitor.py -h
```

or 

```sh
python3 ./instagram_monitor.py -h
```

### Monitoring mode

To monitor specific user activity in [mode 1](#mode-1-without-logged-in-instagram-account) (without logged in Instagram account), just type its Instagram username as parameter (**misiek_to_ja** in the example below):

```sh
./instagram_monitor.py misiek_to_ja
```

To monitor specific user activity in [mode 2](#mode-2-with-logged-in-instagram-account) (with logged in Instagram account), you also need to specify your Instagram account name (**-u**) which you used in *instaloader* tool (*misiek_to_ja_mon* in the example below):

```sh
./instagram_monitor.py -u misiek_to_ja_mon misiek_to_ja
```

The tool will run infinitely and monitor the user until the script is interrupted (Ctrl+C) or killed the other way.

You can monitor multiple Instagram users by spawning multiple copies of the script. 

It is suggested to use sth like **tmux** or **screen** to have the script running after you log out from the server.

The tool automatically saves its output to *instagram_monitor_username.log* file (can be changed in the settings or disabled with **-d** parameter).

The tool in mode 2 also saves the the list of followings & followers to *instagram_username_followings.json* and *instagram_username_followers.json* files, so we do not need to refetch it every time the tool is restarted and so we can also detect changes since last usage of the tool.

## How to use other features

### Email notifications

If you want to get email notifications for different events (new posts & stories, changed followings, bio, errors) use **-s** parameter (works for both modes):

```sh
./instagram_monitor.py misiek_to_ja -s
```

It does not include information about changed followers. For that use **-m** parameter:

```sh
./instagram_monitor.py misiek_to_ja -m
```

Make sure you defined your SMTP settings earlier (see [SMTP settings](#smtp-settings)).

Example email:

<p align="center">
   <img src="./assets/instagram_monitor_email_notifications.png" alt="instagram_monitor_email_notifications" width="60%"/>
</p>


### Saving user activities to the CSV file

If you want to save all Instagram user's activities in the CSV file, use **-b** parameter with the name of the file (it will be automatically created if it does not exist):

```sh
./instagram_monitor.py misiek_to_ja -b instagram_misiek_to_ja.csv
```

### Check interval

If you want to change the check interval to 1 hour (3600 seconds) use **-c** parameter:

```sh
./instagram_monitor.py misiek_to_ja -c 3600
```

It is generally not recommended to use values lower than 1 hour as it will be quickly picked up by Instagram.

In order to make the tool's behaviour less suspicious for Instagram, by default the check interval value is randomly picked from the range: 

[ INSTA_CHECK_INTERVAL (**-c**) - RANDOM_SLEEP_DIFF_LOW (**-i**) ] <-----> [ INSTA_CHECK_INTERVAL (**-c**) +RANDOM_SLEEP_DIFF_HIGH (**-j**) ]

So having the check interval set to 1 hour (-c 3600), RANDOM_SLEEP_DIFF_LOW set to default 15 mins (-i 900) and RANDOM_SLEEP_DIFF_HIGH set to default 3 mins (-j 180) means that the check interval will be with every iteration picked from the range of 45 mins to 1 hour and 3 mins.

Thats why the check interval information is printed in the console and email notifications as it is esentially a random number.

On top of that you can also define that checks should be done in specific hour ranges by setting **CHECK_POSTS_IN_HOURS_RANGE** to True and then defining proper values for **MIN/MAX_H1/H2** variables (see the comments in [instagram_monitor.py](instagram_monitor.py))

### Controlling the script via signals

The tool has several signal handlers implemented which allow to change behaviour of the tool without a need to restart it with new parameters.

List of supported signals:

| Signal | Description |
| ----------- | ----------- |
| USR1 | Toggle email notifications for new posts & stories, changed followings, bio (-s) |
| USR2 | Toggle email notifications for new followers (-m) |
| TRAP | Increase the user activity check interval (by 5 mins) |
| ABRT | Decrease the user activity check interval (by 5 mins) |

So if you want to change functionality of the running tool, just send the proper signal to the desired copy of the script.

I personally use **pkill** tool, so for example to toggle new followers email notifications for tool instance monitoring the *misiek_to_ja* user:

```sh
pkill -f -USR2 "python3 ./instagram_monitor.py misiek_to_ja"
```

### Other

Check other supported parameters using **-h**.

You can combine all the parameters mentioned earlier.

## Limitations

The operation of the tool might flag the Instagram account and/or IP as being an automated tool (as described earlier).

## Colouring log output with GRC

If you use [GRC](https://github.com/garabik/grc) and want to have the output properly coloured you can use the configuration file available [here](grc/conf.monitor_logs)

Change your grc configuration (typically *.grc/grc.conf*) and add this part:

```
# monitoring log file
.*_monitor_.*\.log
conf.monitor_logs
```

Now copy the *conf.monitor_logs* to your .grc directory and instagram_monitor log files should be nicely coloured.

## License

This project is licensed under the GPLv3 - see the [LICENSE](LICENSE) file for details
