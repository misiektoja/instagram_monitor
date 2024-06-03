# instagram_monitor

instagram_monitor is a Python script which allows for real-time monitoring of Instagram users activities and profile changes. 

## Features

- Real-time tracking of Instagram users activities and profile changes:
   - new posts & stories
   - changed followings, followers, bio
   - changed profile pictures
- Anonymous download of user's story images & videos; yes, user won't know you watched their stories 😉
- Download of user's post images & videos
- Email notifications for different events (new posts & stories, changed followings, followers, bio, changed profile pictures, errors)
- Attaching changed profile pictures and stories/posts images directly in email notifications
- Displaying the profile picture and stories/posts images right in your terminal (if you have *imgcat* installed)
- Saving all user activities and profile changes with timestamps to the CSV file
- Support for both public and private profiles
- Two modes of operation: with or without logged in Instagram account
- Different mechanisms to prevent captcha and detection of automated tools
- Possibility to control the running copy of the script via signals

<p align="center">
   <img src="./assets/instagram_monitor.png" alt="instagram_monitor_screenshot" width="90%"/>
</p>

## Change Log

Release notes can be found [here](RELEASE_NOTES.md)

## Disclaimer

I'm not a dev, project done as a hobby. Code is ugly and as-is, but it works (at least for me) ;-)

## Requirements

The script requires Python 3.x.

It uses [instaloader](https://github.com/instaloader/instaloader) library, also requires requests, python-dateutil, pytz and tzlocal.

It has been tested successfully on:
- macOS (Ventura & Sonoma)
- Linux (Raspberry Pi Bullseye & Bookworm based on Debian, Ubuntu 24)
- Windows (10 & 11)

It should work on other versions of macOS, Linux, Unix and Windows as well.

## Installation

Install the required Python packages:

```sh
python3 -m pip install requests python-dateutil pytz tzlocal instaloader
```

Or from requirements.txt:

```sh
pip3 install -r requirements.txt
```

Copy the *[instagram_monitor.py](instagram_monitor.py)* file to the desired location. 

You might want to add executable rights if on Linux/Unix/macOS:

```sh
chmod a+x instagram_monitor.py
```

## Configuration

Edit the  *[instagram_monitor.py](instagram_monitor.py)* file and change any desired configuration variables in the marked **CONFIGURATION SECTION** (all parameters have detailed description in the comments).

### Mode 1 without logged in Instagram account (without session login)

First mode of tool operation assumes you do not log in with your Instagram account to monitor other users. 

This way you can still monitor basic activities of the user like new posts, stories, changed bio and also changed number of followers & followings, but without information what followers/followings have been added or removed. You also won't be able to get more detailed info about new posts & stories.

This mode is easy to use, does not require any preparation and is resistant to Instagram's anti-captcha and automated tool detection mechanisms.

### Mode 2 with logged in Instagram account (with session login)

Second mode of tool operation assumes you use Instagram account to perform session login in the tool to monitor other users. 

This way you can also get information about added/removed followers/followings and more detailed info about new posts and stories.

I suggest to create a new account for the usage with the tool as there is a small risk the account might get banned. However, I use few accounts since more than a year with this tool and all the accounts are still active, but Instagram might present some warnings occasionally about detected suspicious activity.

You can define the username and password directly in the *[instagram_monitor.py](instagram_monitor.py)* file (or via **-u** and **-p** parameters), however it means that session login procedure is performed every time the tool is executed. It is highly recommended to log in once and save the session information using **instaloader** tool. 

Once you installed the instaloader pip package, the needed binary should be available and you can log in as in the example below (user *mon_account*):

```sh
instaloader -l mon_account
```

It will ask for your password and save the session. However, this method presents an issue that after some time Instagram will most likely report detection of an automated tool, especially in case of frequent changes of followers/followings of the monitored users.

To overcome this it is suggested to use the most recommended way - using the session cookie from your web browser. 

Use Firefox web browser, log in to the Instagram account which you want to use to monitor other users and then use *[instaloader_import_firefox_session.py](instaloader_import_firefox_session.py)* tool to import the session from Firefox's *cookies.sqlite* to instaloader (you might have to adjust the path of your Firefox profile in this script). 

This method has an advantage that if you do some activities with this account in your Firefox browser every few days (like scrolling through feed, liking some posts) it will count as "good" activity which will increase reputation of the tool's actions. Sometimes you might still see some warnings in your Firefox web browser where you need to click Dismiss button, but it should not be too often.

### Timezone

The tool will try to automatically detect your local time zone so it can convert Instagram timestamps to your time. 

In case you want to specify your timezone manually then change **LOCAL_TIMEZONE** variable from *'Auto'* to specific location, e.g.

```
LOCAL_TIMEZONE='Europe/Warsaw'
```

In such case it is not needed to install *tzlocal* pip module.

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

To monitor specific user activity in [mode 1](#mode-1-without-logged-in-instagram-account-without-session-login) (without performing session login), just type Instagram username as parameter (**misiek_to_ja** in the example below):

```sh
./instagram_monitor.py misiek_to_ja
```

To monitor specific user activity in [mode 2](#mode-2-with-logged-in-instagram-account-with-session-login) (with session login), you also need to specify your Instagram account name (**-u**) which you used in *instaloader* tool (*mon_account* in the example below):

```sh
./instagram_monitor.py -u mon_account misiek_to_ja
```

The tool will run infinitely and monitor the user until the script is interrupted (Ctrl+C) or killed the other way.

You can monitor multiple Instagram users by spawning multiple copies of the script. 

It is suggested to use sth like **tmux** or **screen** to have the script running after you log out from the server (unless you are running it on your desktop).

The tool automatically saves its output to *instagram_monitor_username.log* file (can be changed in the settings via **INSTA_LOGFILE** variable or disabled completely with **-d** parameter).

The tool in mode 2 (with session login) also saves the list of followings & followers to these files:
- *instagram_username_followings.json*
- *instagram_username_followers.json*

Thanks to this we do not need to re-fetch it every time the tool is restarted and we can also detect changes since last usage of the tool.

The tool also saves the user profile picture to *instagram_{username}_profile_pic\*.jpeg* files.

It also saves downloaded posts images & videos to:
- *instagram_{username}_post_YYYYmmdd_HHMMSS.jpeg*
- *instagram_{username}_post_YYYYmmdd_HHMMSS.mp4*

And downloaded stories images & videos to:
- *instagram_{username}_story_YYYYmmdd_HHMMSS.jpeg*
- *instagram_{username}_story_YYYYmmdd_HHMMSS.mp4*

## How to use other features

### Email notifications

If you want to get email notifications for different events (new posts & stories, changed followings, bio, changed profile picture) use **-s** parameter (works for both modes):

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
   <img src="./assets/instagram_monitor_email_notifications.png" alt="instagram_monitor_email_notifications" width="80%"/>
</p>


### Saving user activities to the CSV file

If you want to save all Instagram user's activities and profile changes in the CSV file, use **-b** parameter with the name of the file (it will be automatically created if it does not exist):

```sh
./instagram_monitor.py misiek_to_ja -b instagram_misiek_to_ja.csv
```

### Detection of changed profile pictures

The tool has functionality to detect changed profile pictures. Proper information will be visible in the console (and email notifications when **-s** parameter is enabled). By default this feature is enabled, but you can disable it either by setting **DETECT_CHANGED_PROFILE_PIC** variable to *False* or by enabling **-k** / **--do_not_detect_changed_profile_pic** parameter.

Since Instagram user's profile picture URL seems to change from time to time, the tool detects changed profile picture by doing binary comparison of saved jpeg files. Initially it saves the profile pic to *instagram_{username}_profile_pic.jpeg* file after the tool is started, then during every check the new picture is fetched and the tool does binary comparison if it has changed or not.

In case of changes the old profile picture is moved to *instagram_{username}_profile_pic_old.jpeg* file and the new one is saved to *instagram_{username}_profile_pic.jpeg* and also to the file named *instagram_{username}_profile_pic_YYmmdd_HHMM.jpeg* (so we can have history of all profile pictures).

The tool also has built-in detection of empty profile pictures. Instagram does not signal the fact of empty user's profile image in their API, that's why we can detect it by using empty profile image template (which seems to be the same on binary level for all users).

To use this feature put [instagram_profile_pic_empty.jpeg](instagram_profile_pic_empty.jpeg) file in the dir from which you run the script. This way the tool will be able to detect when user does not have profile image set. 

It is not mandatory, but highly recommended as otherwise the tool will treat empty profile pic as regular one, so for example user's removal of profile picture will be detected as changed profile picture.

### Displaying profile / posts / stories images in your terminal

if you have *imgcat* installed you can enable the feature displaying profile pictures and stories/posts images right in your terminal. For that put path to your *imgcat* binary in **IMGCAT_PATH** variable (or leave it empty to disable this functionality).

### Check interval

If you want to change the check interval to 1 hour (3600 seconds) use **-c** parameter:

```sh
./instagram_monitor.py misiek_to_ja -c 3600
```

It is generally not recommended to use values lower than 1 hour as it will be quickly picked up by Instagram automated tool detection mechanisms.

In order to make the tool's behavior less suspicious for Instagram, by default the check interval value is randomly picked from the range: 

[ INSTA_CHECK_INTERVAL (**-c**) - RANDOM_SLEEP_DIFF_LOW (**-i**) ] <-----> [ INSTA_CHECK_INTERVAL (**-c**) + RANDOM_SLEEP_DIFF_HIGH (**-j**) ]

So having the check interval set to 1 hour (-c 3600), RANDOM_SLEEP_DIFF_LOW set to default 15 mins (-i 900) and RANDOM_SLEEP_DIFF_HIGH set to default 3 mins (-j 180) means that the check interval will be with every iteration picked from the range of 45 mins to 1 hour and 3 mins.

That's why the check interval information is printed in the console and email notifications as it is essentially a random number.

On top of that you can also define that checks for new posts should be done only in specific hour ranges by setting **CHECK_POSTS_IN_HOURS_RANGE** to True and then defining proper values for **MIN/MAX_H1/H2** variables (see the comments in [instagram_monitor.py](instagram_monitor.py) file for more information).

### Controlling the script via signals (only macOS/Linux/Unix)

The tool has several signal handlers implemented which allow to change behavior of the tool without a need to restart it with new parameters.

List of supported signals:

| Signal | Description |
| ----------- | ----------- |
| USR1 | Toggle email notifications for new posts & stories, changed followings, bio, profile picture (-s) |
| USR2 | Toggle email notifications for new followers (-m) |
| TRAP | Increase the user activity check interval (by 5 mins) |
| ABRT | Decrease the user activity check interval (by 5 mins) |

So if you want to change functionality of the running tool, just send the proper signal to the desired copy of the script.

I personally use **pkill** tool, so for example to toggle new followers email notifications for the tool instance monitoring the *misiek_to_ja* user:

```sh
pkill -f -USR2 "python3 ./instagram_monitor.py misiek_to_ja"
```

As Windows supports limited number of signals, this functionality is available only on Linux/Unix/macOS.

### Other

Check other supported parameters using **-h**.

You can combine all the parameters mentioned earlier.

## Limitations

The operation of the tool might flag the Instagram account and/or IP as being an automated tool (as described earlier).

## Coloring log output with GRC

If you use [GRC](https://github.com/garabik/grc) and want to have the tool's log output properly colored you can use the configuration file available [here](grc/conf.monitor_logs)

Change your grc configuration (typically *.grc/grc.conf*) and add this part:

```
# monitoring log file
.*_monitor_.*\.log
conf.monitor_logs
```

Now copy the *conf.monitor_logs* to your *.grc* directory and instagram_monitor log files should be nicely colored when using *grc* tool.

## License

This project is licensed under the GPLv3 - see the [LICENSE](LICENSE) file for details
