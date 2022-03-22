from pywitch import PyWitchTMI, run_forever
from pywitch import PyWitchStreamInfo
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import logging
import atexit
import time
import csv
import requests
from datetime import datetime


# channel id arrays - im pretty sure there is a way to get this programatically through the api providing just the channel name, do this later. At the very lest store them in a file....
channel_ids = {
    "xqcow": 71092938,
    "ahrelevant": 189362827,
    "destiny": 18074328,
    "asmongold": 26261471,
    "lec": 124422593,
    "jokerdtv": 48082917,
    "dylanburnstv": 468777657,
    "dancantstream": 92189556,
    "mrgirlreturns": 648955095,
    "stardust": 178851824,
    "primecayes": 522815466,
    "daskrubking": 125488902,
    "mindwavestv": 104832740,
    "mrmouton": 45686481,
    "dunkstream": 40397064,
    "imreallyimportant": 43701021,
    "heem": 464207300,
    "jadeisaboss": 65346556,
    "gappyv": 24261684,
    "realdancody": 680342560,
    "criticallythinkingveteran": 559203104,
    "codemiko": 500128827,
    "melina": 409624608,
    "pisco95": 87659021,
    "ragepope": 453444909,
    "moderndatdebate": 455406802,
    "erisann": 22734935,
    "chaeiry": 618636970,
    "sondsol": 57374878,
    "eristocracytv": 88527017,
    "hasanabi": 207813352,
    "chudlogic": 473514006,
    "rose_wrist": 433864363,
    "rileygraceroshong": 554423691,
    "lycangtv": 68798125,
    "hanzofharkir": 539698749,
    "jahmillionaire": 26229743,
    "anavoir": 457863917,
    "infraredshow": 643119348,
    "kyootbot": 161737008,
    "jonzherka": 407881598,
    "remthebathboi": 82986547,
    "esl_csgo": 31239503,

    "cindr": 55294253
}


# settings
clip_threshold = 1.8  # percent of avg chat activity needed to trigger clip, 1.0 is 100% (exactly the average).
chat_count_trap_length = 1000
chat_count_trap_time = 20
chat_increase_list_length = 50
lockout_timer = 20

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

# setup loggers
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

### NEW IDEA - Setup channels as classes with each channel being an individual object, then just list objects and run them through the list.
# we can store channel name, id, clips, stats even inside objects and use commands based system - "add channel x" "open clips channel x" "start clipper" to do whatever we want.
class Channel:


    def __init__(self, _channel_name):
        self.channel_name = _channel_name
        self.id = "offline" # init here as offline so we can catch, gets set in setup_info()
        self.setup_info()
        self.chat_count = 1  # we start at 1 to avoid 'divide by zero' problems on chat_count_past
        self.chat_count_past = 1
        self.chat_count_trap = []
        self.chat_count_increase = 0
        self.chat_count_increase_frac = 0
        self.chat_count_difference = 0
        self.chat_increase_list = []
        self.chat_increase_avg = 0
        self.lockout = 0


    # chat info callback - get info from stream (same as running GET https://api.twitch.tv/helix/users?login=<login name>&id=<user ID> api call)
    def info_callback(self, data):
        print("\n -- setting channel info for " + self.channel_name + ": ")
        print(data)
        self.id = data["user_id"]


    # setup channel info - returns channel info dictionary (data) via callback above.
    def setup_info(self):
        global user_token
        global users
        streaminfo = PyWitchStreamInfo(
            channel = self.channel_name,
            token = user_token,
            callback = self.info_callback,
            users = users,
            interval = 1,
            verbose = True
        )
        streaminfo.start()


    # tmi callback - runs everytime messages are sent to the twitch chat
    def tmi_callback(self, data):
        # data looks like: ['display_name', 'event_time', 'user_id', 'login', 'message', 'event_raw']
        print("    " + str(data))
        chat_logger.info(data['display_name'] + ": " + data["message"])
        self.chat_count += 1


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
        # tmi.send(' ~ connected ~ ') # send message in chat example


    # trigger making clip
    def get_clip(self):
        global twitch

        # print some stuff so we see the clip happen when watching terminal
        print("CREATING CLIP!!!!!!!!!!!!!!!!!")
        print("CLIPPPPPPPP")
        print("CLIPPPPPPPP")

        # create clip
        clip = twitch.create_clip(self.id, False)

        # print clip data to terminal
        print(clip)
        print(clip['data'][0]['edit_url'])

        # write to log
        clip_logger.info(self.channel_name + " | " + clip["data"][0]["edit_url"] + " ~ (inc: " + str(
            self.chat_count_increase) + ", avg: " + str(round(self.chat_increase_avg, 2)) + " diff:" + str(
            round(self.chat_count_increase / self.chat_increase_avg, 2)) + ")")

        # write to csv
        clip_row = [self.channel_name, clip["data"][0]["edit_url"], str(self.chat_count_increase),
                    str(round(self.chat_increase_avg, 2)), str(round(self.chat_count_increase / self.chat_increase_avg, 2)),
                    datetime.now()]
        clips_write.writerow(clip_row)


# setup channels
target_channels = []
target_channels.append(Channel("destiny"))
target_channels.append(Channel("asmongold"))
target_channels.append(Channel("ahrelevant"))
target_channels.append(Channel("xqcow"))
target_channels.append(Channel("knut"))
target_channels.append(Channel("jonzherka"))
target_channels.append(Channel("cowsep"))
target_channels.append(Channel("kyootbot"))
target_channels.append(Channel("hasanabi"))
target_channels.append(Channel("rose_wrist"))
target_channels.append(Channel("payo"))
target_channels.append(Channel("echo_esports"))
target_channels.append(Channel("stardust"))
target_channels.append(Channel("wickedsupreme"))
target_channels.append(Channel("primecayes"))
target_channels.append(Channel("davidpakman"))
target_channels.append(Channel("lumirue"))
target_channels.append(Channel("mindwavestv"))
target_channels.append(Channel("booksmarts"))
target_channels.append(Channel("mrmouton"))
target_channels.append(Channel("dunkstream"))
target_channels.append(Channel("devinnash"))
target_channels.append(Channel("imreallyimportant"))
target_channels.append(Channel("jadeisaboss"))
target_channels.append(Channel("livagar"))
target_channels.append(Channel("gappyv"))
target_channels.append(Channel("denims"))
target_channels.append(Channel("katarana_"))
target_channels.append(Channel("realdancody"))
target_channels.append(Channel("criticallythinkingveteran"))
target_channels.append(Channel("melina"))
target_channels.append(Channel("adrianahlee"))
target_channels.append(Channel("pisco95"))
target_channels.append(Channel("ragepope"))
target_channels.append(Channel("thesillyserious"))
target_channels.append(Channel("moderndaydebate"))
target_channels.append(Channel("erisann"))
target_channels.append(Channel("dancantstream"))
target_channels.append(Channel("chaeiry"))
target_channels.append(Channel("eristocracytv"))
target_channels.append(Channel("hanzofharkir"))
target_channels.append(Channel("remthebathboi"))
target_channels.append(Channel("lonerbox"))
target_channels.append(Channel("infraredshow"))
target_channels.append(Channel("anavoir"))




'''
try:
    channel_count = int(input("how many channels do you want to track?"))
except Exception:
    channel_count = 1
    pass
target_channels = []
target_channels_id = []
for c in range(0,channel_count):
    try:
        target_channels.append(input("enter name for channel " + str(c) + "\n"))
    except Exception:
        target_channels.append("esl_csgo")
        pass
    try:
        target_channels_id.append(channel_ids[target_channels[c]])
    except:
        target_channels_ids.append(input("enter channel id for " + target_channels[c] + "\n"))
        pass

print("channels: " + str(target_channels))
print("channels_id: " + str(target_channels_id))
'''

'''
try:
    target_channels = input("enter channel name (as it appears in their url): \n")
except Exception:
    target_channel = "esl_csgo"
    pass
try:
    target_channel_id = channel_ids[target_channel]
except Exception:
    # target_channel_id = 71092938  # cindr:55294253
    target_channel_id = input("enter the channel id for " + target_channel + ": \n")
    pass
'''


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
            # t.setup_tmi()

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
                if t.chat_count_increase > (clip_threshold * t.chat_increase_avg) and len(t.chat_count_trap) > (chat_count_trap_length*0.1) and t.id != "offline" and t.lockout == 0 :
                    t.lockout = lockout_timer
                    try: t.get_clip()
                    except (TwitchAPIException) as error:
                        clip_logger.info(self.channel_name + " | " + "CLIP FAILED: " + error + " ~ (inc: " + str(
                            self.chat_count_increase) + ", avg: " + str(
                            round(self.chat_increase_avg, 2)) + " diff:" + str(
                            round(self.chat_count_increase / self.chat_increase_avg, 2)) + ")")


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