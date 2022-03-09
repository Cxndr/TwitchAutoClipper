from pywitch import PyWitchTMI, run_forever
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import logging
import atexit
import time
import csv
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
clip_threshold = 1.8
chat_count_trap_length = 1000
chat_count_trap_time = 20
chat_increase_list_length = 50
lockout_timer = 20


# variable setup
app_id = "f81skqyv28rzas6nqj3nvzaq9x3tqs"
secret = "w3rnpwvpbiiw9lb1co497mm6goqla8"
user_token = "x7jxalqa8wahy06q846xt4b6iwcley"
users = {} # shared user list minimizes the number of requests
try:
    target_channel = input("enter channel name (as it appears in their url): \n")
except Exception:
    target_channel = "esl_csgo"
    pass
try:
    target_channel_id = channel_ids[target_channel]
except Exception:
    # target_channel_id = 71092938  # cindr:55294253
    target_channel_id = input("enter the channel id for " + target_channel + ": \n")
    pass
twitch = Twitch(app_id, secret)
chat_count = 1  # we start at 1 to avoid 'divide by zero' problems on chat_count_past
chat_count_past = 1
chat_count_trap = []
chat_count_increase = 0
chat_count_increase_frac = 0
chat_increase_list = []
chat_increase_avg = 0
lockout = 0


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


# tmi callback (runs everytime messages are sent to the twitch chat)
def callback(data):
    # data looks like: ['display_name', 'event_time', 'user_id', 'login', 'message', 'event_raw']
    global chat_count
    print( "    " + str(data) )
    chat_logger.info( data['display_name'] + ": " + data["message"])
    chat_count += 1


# trigger making clip
def get_clip():

    global twitch

    # print some stuff so we see the clip happen when watching terminal
    print("CREATING CLIP!!!!!!!!!!!!!!!!!")
    print("CLIPPPPPPPP")
    print("CLIPPPPPPPP")
    print("CLIPPPPPPPP")
    print("CLIPPPPPPPP")
    print("CLIPPPPPPPP")
    print("CLIPPPPPPPP")
    print("CLIPPPPPPPP")

    # create clip
    clip = twitch.create_clip(target_channel_id,False)

    # print clip data to terminal
    print(clip)
    print(clip['data'][0]['edit_url'])

    # write to log
    clip_logger.info( target_channel + " | " + clip["data"][0]["edit_url"] + " ~ (inc: " + str(chat_count_increase) + ", avg: " + str(round(chat_increase_avg,2)) + " diff:" + str(round(chat_count_increase/chat_increase_avg,2)) + ")" )

    # write to csv
    clip_row = [target_channel, clip["data"][0]["edit_url"], str(chat_count_increase), str(round(chat_increase_avg,2)), str(round(chat_count_increase/chat_increase_avg,2)), datetime.now() ]
    clips_write.writerow(clip_row)

# setup tmi (class that returns chat messages)
tmi = PyWitchTMI(
    channel = target_channel,
    token = user_token,
    callback = callback, # Optional
    users = users,       # Optional, but strongly recomended
    verbose = True,      # Optional
)
tmi.start()
#tmi.send(' ~ connected ~ ') # send message in chat example


# chat count loop
while True:

    try:
        # store current chat count into trap list (position 0)
        chat_count_trap.insert(0,chat_count)

        # destroy last trap if full
        if len(chat_count_trap) >= chat_count_trap_length:
            chat_count_trap.pop()

        # set past chat value based on trap_time
        if len(chat_count_trap) > chat_count_trap_time:
            chat_count_past = chat_count_trap[chat_count_trap_time-1]
        else: chat_count_past = 1

        # set count increase since past count and turn into percentage/decimal
        chat_count_increase = chat_count - chat_count_past
        if chat_count_increase > 0:
            chat_count_increase_frac = chat_count_increase / chat_count_past
        else: chat_count_increase_frac = 0

        # add count increase to avg list, remove if above max length
        if chat_count_increase > 0:
            chat_increase_list.insert(0, chat_count_increase)
        if len(chat_increase_list) >= chat_increase_list_length:
            chat_increase_list.pop()

        # calculate average increase
        if len(chat_increase_list) > 0:
            chat_increase_avg = sum(chat_increase_list) / len(chat_increase_list)
        print( "\n current:" + str(chat_count) + " past:" + str(chat_count_past) + " increase:" + str(chat_count_increase) + " inc_frac:" + str(round(chat_count_increase_frac,2)) + " avg_inc:" + str(round(chat_increase_avg,2)) + "\n" )

        # if increase is x bigger than avg increase then trigger clip
        if chat_count_increase > (clip_threshold * chat_increase_avg) and len(chat_count_trap) > (chat_count_trap_length*0.1) and lockout == 0:
            lockout = lockout_timer
            get_clip()

        # move lockout timer
        if lockout > 0:
            lockout -= 1

        # Wait 1 sec
        time.sleep(1)

    except (KeyboardInterrupt, SystemExit) as e:
        cleanup_chatloop()

# run forever (for pywitch tmi) - not nessecary when checking ticker in loop
#run_forever()
