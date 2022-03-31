from pywitch import PyWitchTMI, run_forever
from pywitch import PyWitchStreamInfo
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
from twitchAPI.types import TwitchAPIException
import logging
import atexit
import time
import csv
import requests
from datetime import datetime

# settings
clip_threshold = 1.7  # percent of avg chat activity needed to trigger clip, 1.0 is 100% (exactly the average).
chat_count_trap_length = 100 # default 1000, using lower for fast testing
chat_count_trap_time = 20
chat_increase_list_length = 10
lockout_timer = 20
settings_track_offline_channels = True

# variable setup
app_id = "f81skqyv28rzas6nqj3nvzaq9x3tqs"
secret = "w3rnpwvpbiiw9lb1co497mm6goqla8"
user_token = "x7jxalqa8wahy06q846xt4b6iwcley"
users = {} # shared user list minimizes the number of requests
twitch = Twitch(app_id, secret)

# TwitchAPI package authentication
target_scope = [AuthScope.CLIPS_EDIT]
auth = UserAuthenticator(twitch, target_scope, force_verify=False)
token, refresh_token = auth.authenticate() # this will open your default browser and prompt you with the twitch verification website
twitch.set_user_authentication(token, target_scope, refresh_token) # add User authentication

# clean up
def cleanup_chatloop():
    # close clips csv
    clips_csv.close()
atexit.register(cleanup_chatloop)

# open clips csv
clips_csv = open("clips.csv", "a", encoding="UTF8", newline="")
clips_write = csv.writer(clips_csv)

# setup general loggers - channel specific ones setup in channel class.
formatter = logging.Formatter('%(asctime)s - %(message)s')
def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""
    handler = logging.FileHandler(log_file, encoding='utf-8')
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger
chat_logger = setup_logger('chatlog', 'chat.log')
clip_logger = setup_logger('clipslog', 'clips.log')
main_logger = setup_logger('mainlog', 'main.log')

### NEW IDEA - Setup channels as classes with each channel being an individual object, then just list objects and run them through the list.
# we can store channel name, id, clips, stats even inside objects and use commands based system - "add channel x" "open clips channel x" "start clipper" to do whatever we want.
class Channel:

    def __init__(self, _channel_name):

        self.channel_name = _channel_name
        self.channel_info = twitch.get_users(logins=[self.channel_name])
        self.id = self.channel_info['data'][0]['id']
        # self.broadcast_info = twitch.get_channel_information(broadcaster_id=[self.id])
        self.stream_info = twitch.get_streams(user_id=[self.id])
        print(self.stream_info)

        self.chat_count = 1  # we start at 1 to avoid 'divide by zero' problems on chat_count_past
        self.chat_count_past = 1
        self.chat_count_trap = []
        self.chat_count_increase = 0
        self.chat_count_increase_frac = 0
        self.chat_count_difference = 0
        self.chat_increase_list = []
        self.chat_increase_avg = 0
        self.lockout = 0
        self.channel_chat_logger = setup_logger(self.channel_name + '_chatlog', 'channel_logs/' + self.channel_name + '_chat.log')

    def channel_is_offline(self):
        if not self.stream_info['data']:
            return True
        else:
            return False

    # chat info callback - get info from stream (same as running GET https://api.twitch.tv/helix/users?login=<login name>&id=<user ID> api call)
    def info_callback(self, data):
        print("\n -- setting channel info for " + self.channel_name + ": ")
        print(data)
        self.id = data["user_id"]

    # setup channel info - returns channel info dictionary (data) via callback above.
        # IS THIS STILL NESSESARY? We are using twitch.get_users to retrive channel info as needed.
        # May be needed to check if a channel is still online or offline - could we again just check online/offline status with a twitch.___ api call????
    def setup_info(self):
        global user_token
        global users
        target_info = PyWitchStreamInfo(
            channel = self.channel_name,
            token = user_token,
            callback = self.info_callback,
            users = users,
            interval = 1,
            verbose = True
        )
        target_info.start()

    # tmi callback - runs everytime messages are sent to the twitch chat
    def tmi_callback(self, data):
        # data looks like: ['display_name', 'event_time', 'user_id', 'login', 'message', 'event_raw']
        print("    " + str(data))
        self.chat_count += 1
        chat_logger.info( "chat_count:" + str(self.chat_count) + " [" + self.channel_name + "] [" + data['display_name'] + "] " + data['message'] )
        self.channel_chat_logger.info( "chat_count:" + str(self.chat_count) + " [" + self.channel_name + "] [" + data['display_name'] + "] " + data['message'])


    # setup tmi (twitch messaging interface) - returns chat messages with their data via callback above.
    def setup_tmi(self):
        global user_token
        global users
        tmi = PyWitchTMI(
            channel=self.channel_name,
            token=user_token,
            callback=self.tmi_callback,  # Optional
            users=users,  # Optional, but strongly recomended
            verbose=True,  # Optional
        )
        tmi.start()
        # tmi.send(' OOOO ') # send message in chat example

    # make clip
    def get_clip(self):

        clip_trigger_info = \
            " ~ (inc:" + str(self.chat_count_increase) \
            + ", avg:" + str(round(self.chat_increase_avg, 2)) \
            + ", diff:" + str(round(self.chat_count_increase / self.chat_increase_avg, 2)) \
            + ")"

        # dont make clip (return) if channel is offline
        if self.channel_is_offline():
            error_clip_offline = self.channel_name + " | [CLIP CREATE FAILED]: Channel Offline" + clip_trigger_info
            clip_logger.info(error_clip_offline)
            print( "Error: " + str(error_clip_offline) )
            return

        global twitch

        # print some stuff so we see the clip happen when watching terminal
        print("CREATING CLIP!!!!!!!!!!!!!!!!!")
        print("CLIPPPPPPPP")
        print("CLIPPPPPPPP")

        # create clip
        try:
            clip = twitch.create_clip(self.id, False)
            if 'error' in clip.keys():
                raise TwitchAPIException(clip)
        except TwitchAPIException as error:
            clip_logger.info( self.channel_name + " | [CLIP CREATE FAILED]: " + str(error) + clip_trigger_info )
            print( "Error: " + str(error) )
            return
        else: # print feedback to terminal
            print(clip)
            print(clip['data'][0]['edit_url'])

        # write to log
        clip_logger.info( self.channel_name + " | " + clip["data"][0]["edit_url"] + clip_trigger_info )

        # write to csv
        clip_row = [self.channel_name, clip["data"][0]["edit_url"], str(self.chat_count_increase),
                    str(round(self.chat_increase_avg, 2)), str(round(self.chat_count_increase / self.chat_increase_avg, 2)),
                    datetime.now()]
        clips_write.writerow(clip_row)


# setup channels
target_channels = []

def load_channels():
    with open('target_channels.txt', 'r') as file_object:
        file_contents = file_object.readlines()
        for line in file_contents:
            channel_name = line.strip()
            if line.strip() and not channel_name.startswith('#'): # "if line.strip()" checks for blank lines! #pythonic pepeW
                #channel_name = line.rstrip() # remove line break which is the last character of the string
                channel_info = twitch.get_users(logins=[channel_name])
                print(channel_info)
                if channel_info['data']: # check if channel returns a data array for channel info
                    target_channels.append(Channel(channel_name))
                else:
                    channel_error = "Error adding channel [" + channel_name + "], no channel id data recieved, is the channel banned or the name typed incorrectly?"
                    print(channel_error)
                    main_logger.info(channel_error)

def add_channel(*args):
    for c in range(len(args)):
        channel_info = twitch.get_users(logins=[c])
        if channel_info['data']: # check if channel returns a data array for channel info
            target_channels.append(Channel(args[c]))
        with open('target_channels.txt', 'a+') as file_object:
            file_object.seek(0) # go to start of file
            data = file_object.read(100)
            if len(data) > 0: # if file is empty write new line
                file_object.write("\n")
            file_object.write(args[c])

load_channels()
print(target_channels)

# run program
def run_clipper():

    # setup tmi for chat loops
    for i in range(len(target_channels)):
        t = target_channels[i]
        t.setup_tmi()

    # chat count loop
    while True:

        for i in range(len(target_channels)):

            t = target_channels[i]

            # dont process offline channels
            if settings_track_offline_channels:
                if t.channel_is_offline():
                    print(" [" + t.channel_name + "] - Channel Offline")
                    continue

            try:

                # store current chat count into trap list (position 0)
                t.chat_count_trap.insert(0,t.chat_count)

                # destroy last trap if full
                if len(t.chat_count_trap) >= chat_count_trap_length:
                    t.chat_count_trap.pop()

                # set past chat value based on trap_time
                if len(t.chat_count_trap) > chat_count_trap_time:
                    t.chat_count_past = t.chat_count_trap[chat_count_trap_time-1]
                else: t.chat_count_past = 1

                # set count increase since past count and turn into percentage/decimal
                t.chat_count_increase = t.chat_count - t.chat_count_past
                if t.chat_count_increase > 0:
                    t.chat_count_increase_frac = t.chat_count_increase / t.chat_count_past
                else: t.chat_count_increase_frac = 0

                # add count increase to avg list, remove if above max length
                if t.chat_count_increase > 0:
                    t.chat_increase_list.insert(0, t.chat_count_increase)
                if len(t.chat_increase_list) >= chat_increase_list_length:
                    t.chat_increase_list.pop()

                # calculate average increase, represent as fraction, then print feedback
                if len(t.chat_increase_list) > 0:
                    t.chat_increase_avg = sum(t.chat_increase_list) / len(t.chat_increase_list)
                if t.chat_count_increase > 0 and t.chat_increase_avg > 0: # to avoid divide by zero error
                    t.chat_count_difference = round(t.chat_count_increase / t.chat_increase_avg, 2)
                else: t.chat_count_difference = 0
                print( "\n channel:" + t.channel_name
                       + " current:" + str(t.chat_count)
                       + " past:" + str(t.chat_count_past)
                       + " increase:" + str(t.chat_count_increase)
                       + " inc_frac:" + str(round(t.chat_count_increase_frac,2))
                       + " avg_inc:" + str(round(t.chat_increase_avg,2))
                       + " diff:" + str(t.chat_count_difference)
                       + " lockout:" + str(t.lockout)
                       + " trap_len:" + str(len(t.chat_count_trap)) + "\n" )

                # if increase is x bigger than avg increase then trigger clip
                if t.chat_count_increase > (clip_threshold * t.chat_increase_avg) and len(t.chat_count_trap) > (chat_count_trap_length*0.1) and t.lockout == 0 :
                    t.lockout = lockout_timer
                    t.get_clip()

                # move lockout timer
                if t.lockout > 0:
                    t.lockout -= 1

                # wait 1 sec
                time.sleep(1)

            except (KeyboardInterrupt, SystemExit) as e:
                cleanup_chatloop()

    # run forever (for pywitch tmi) - not nessecary when checking tmi in loop, needed for continually running the tmi outside of a loop though.
    #run_forever()

run_clipper()
