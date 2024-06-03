# instagram_monitor release notes

This is a high-level summary of the most important changes. 

# Changes in 1.1 (03 Jun 2024)

**Features and Improvements**:

- **NEW:** Support for **detecting multiple stories** (if session login is used)
- **NEW:** **Fully anonymous download of user's story images & videos** (thumbnail image will be also attached in email notifications and displayed in the terminal if imgcat is installed); yes, user won't know you watched their stories 😉
- **NEW:** **Download of user's post images & videos** (thumbnail image will be also attached in email notifications and displayed in the terminal if imgcat is installed)
- **NEW:** **Detection of changed profile pictures**; since Instagram user's profile picture URL seems to change from time to time, the tool detects changed profile picture by doing binary comparison of saved jpeg files; initially it saves the profile pic to *instagram_{user}_profile_pic.jpeg* file after the tool is started; then during every check the new picture is fetched and the tool does binary comparison if it has changed or not; in case of changes the old profile picture is moved to *instagram_{user}_profile_pic_old.jpeg* file and the new one is saved to *instagram_{user}_profile_pic.jpeg* and also to file named *instagram_{user}_profile_pic_YYmmdd_HHMM.jpeg* (so we can have history of all profile pictures); in order to control the feature there is a new **DETECT_CHANGED_PROFILE_PIC** variable set to True by default; the feature can be disabled by setting it to *False* or by enabling **-k** / **--do_not_detect_changed_profile_pic** parameter
- **NEW:** **Detection of empty profile pictures**; Instagram does not signal the fact of empty user's profile image in their API, that's why we can detect it by using empty profile image template (which seems to be the same on binary level for all users); to use this feature put [instagram_profile_pic_empty.jpeg](instagram_profile_pic_empty.jpeg) file in the dir from which you run the script; this way the tool will be able to detect when user does not have profile image set; it is not mandatory, but highly recommended as otherwise the tool will treat empty profile pic as regular one, so for example user's removal of profile picture will be detected as changed profile picture
- **NEW:** **Attaching changed profile pics and stories/posts images directly in email notifications** (when **-s** parameter is used)
- **NEW:** Feature allowing to **display the profile picture and stories/posts images right in your terminal** (if you have *imgcat* installed); put path to your *imgcat* binary in **IMGCAT_PATH** variable (or leave it empty to disable this functionality)
- **IMPROVEMENT:** Improvements for running the code in **Python under Windows**
- **NEW:** **Automatic detection of local timezone** if you set LOCAL_TIMEZONE variable to 'Auto' (it is default now); requires tzlocal pip module
- **NEW:** Support for honoring last-modified timestamp for saved profile pics (it turned out it reflects timestamp when the picture has been actually added by the user)
- **IMPROVEMENT:** Information about time zone and posts checking hours is displayed in the start screen now
- **NEW:** Fetching of post's location and comments + likes list is back (however needs to be enabled via -t parameter as it highly increases the risk that Instagram will mark the account as an automated tool)
- **NEW:** Added new parameter **-r** / **--skip_getting_story_details** to skip getting detailed info about stories and its images/videos, even if session login is used; you will still get generic information about new stories in such case
- **NEW:** Added new parameter **-t** / **--get_more_post_details** to get more detailed info about new posts like its location and comments + likes list, only possible if session login is used; if not enabled you will still get generic information about new posts; it is disabled by default as for some unknown reasons it highly increases the risk of the account being flagged as an automated tool
- **NEW:** Added new parameter **-k** / **--do_not_detect_changed_profile_pic** which allows to disable detection of changed user's profile picture
- **IMPROVEMENT:** Email sending function send_email() has been rewritten to detect invalid SMTP settings + possibility to attach images
- **IMPROVEMENT:** Strings converted to f-strings for better code visibility
- **IMPROVEMENT:** Rewritten get_date_from_ts(), get_short_date_from_ts(), get_hour_min_from_ts() and get_range_of_dates_from_tss() functions to automatically detect it time object is timestamp (int/float) or datetime
- **IMPROVEMENT:** Better checking for wrong command line arguments
- **IMPROVEMENT:** Help screen reorganization
- **IMPROVEMENT:** pep8 style convention corrections

**Bug fixes**:

- **BUGFIX:** Improved exception handling while processing JSON files
- **BUGFIX:** Escaping of potentially dangerous variables in HTML email templates
- **BUGFIX:** Fix for saving empty followers/followings list to JSON file when the tool is started and Instagram API returns empty list

# Changes in 1.0 (25 Apr 2024)

**Features and Improvements**:

- Improvements in monitoring Instagram user activity without session
- Support for Instagram users having no posts yet
- Support for better handling of private profiles

**Bug fixes**:

- Disabled fetching location, list of likes and comments for posts due to errors after recent Instagram changes (HTTP Error 400)
