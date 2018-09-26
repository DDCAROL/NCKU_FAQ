#coding:utf-8
import os
import sys
import json
import editdistance
import threading, time
import template_json
import urllib2
import urllib
import re

import requests
from flask import Flask, request
from send_msg import sendtofb
from set_workflow import set_temp

app = Flask(__name__)

user_dict = {}
thread_flag = False

def check_user_status():
    global user_dict
    while True :
        for key in user_dict.keys() :
            if time.time() - user_dict[key] > 1800 :
                user_dict.pop(key, None)

        time.sleep(1800)



@app.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route('/', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    global thread_flag   #only run this thread one time
    global user_dict
    if not thread_flag :
        threading.Thread(target = check_user_status, args = (), name = 'check_thread').start()
        thread_flag = True


    data = request.get_json()
    log(data)  # you may not want to log every incoming message in production, but it's good for testing

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):  # someone sent us a message

                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    if "text" in messaging_event["message"] :
                        message_text = messaging_event["message"]["text"]  # the message's text
                        message_text = message_text.encode('utf-8').lower()

                        # dorm internet workflow
                        if "quick_reply" in messaging_event["message"] :
                            payload = messaging_event["message"]["quick_reply"]["payload"]
                            if payload == 'GOT_IT' :
                                send_message( sender_id, '很高興能為你幫上忙' )
                            elif payload == 'ROLL_BACK' :
                                faq = template_json.Template_json(sender_id,template_type=2,
                                      text="是否曾申請過帳號呢? (請用是/否按扭回答以便記錄)", payload_yes = "START_STATE_YES", payload_no = "START_STATE_NO" )
                                send_template_message( faq )
                            else :
                                reply = set_temp(payload, sender_id)
                                send_template_message( reply )

                        else :
                            reply = handle_message( message_text, sender_id )

                            for key in user_dict.keys() :
                                print(key)
                                print(user_dict[key])

                            if not sender_id in user_dict : # not in time interval
                                #暫時拿掉限制
                                #if reply == '抱歉> < 我還無法處理這個問題，請您等待專人為您回答 ' : user_dict[sender_id] = time.time() #使用者待專人回答, chatbot對該使用者暫停
                                if type(reply) == str :
                                    send_message( sender_id, reply )
                                else : #template
                                    send_template_message(reply)
                            pass

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    message_text = messaging_event["postback"]["payload"]  # the message's text
                    message_text = message_text.encode('utf-8').lower()
                    reply = handle_message( message_text, sender_id )
                    if not sender_id in user_dict : # not in time interval
                        user_dict[sender_id] = time.time()
                        send_message( sender_id, reply )

    return "ok", 200

def handle_message(message_text, sender_id):
    global user_dict
    ip = re.findall( r'[0-9]+(?:\.[0-9]+){3}', message_text )

    if u'不是我要的答案'.encode("utf8") in message_text :
        return '請您等待專人為您回答 '


    if u'你好'.encode("utf8") in message_text or u'請問'.encode("utf8") in message_text or u'嗨'.encode("utf8") in message_text or u'哈囉'.encode("utf8") in message_text or 'hi' in message_text or 'hello' in message_text:
        if len(message_text ) < 10:
            return '你好！\n請問我能為您做些什麼？ '
    # Email
    

    #電腦教室開放時間
    if u'電腦'.encode("utf8") in message_text or u'教室'.encode("utf8") in message_text or u'中心'.encode("utf8") in message_text :
        if u'開'.encode("utf8") in message_text or u'用'.encode("utf8") in message_text or u'借'.encode("utf8") in message_text :
            return '您好  電腦教室相關訊息請參考 http://cc.ncku.edu.tw/files/11-1255-3303.php?Lang=zh-tw ，謝謝。'

    #dorm
    if u'宿'.encode("utf8") in message_text :
        if 'p2p' in message_text :
            return '您好  因使用P2P有侵權問題, 本校校園網路禁止使用P2P, 故本校宿網亦禁止使用P2P, 除非是特殊學術用途之使用, 可另行申請.'
        if u'故障'.encode("utf8") in message_text or u'網路孔'.encode("utf8") in message_text :
            return '您好  若確認網路有故障，麻煩至http://dorm.cc.ncku.edu.tw/ 進行使用者登入後進行故障申告，會由工程師為你處理，請耐心等候'
        if 'authentication failed' in message_text :
            return '您好  出現 "Authentication failed." 訊息, 有二種可能: 1. 帳號或密碼輸入錯誤，請重新輸入再試一下。若不確定是否正確，可借室友電腦登入宿網管理系統看看。 \n2. 帳號被停用，登入宿網管理系統，查詢登錄資料，若被停用，在最後一項”特殊限制”中，會註明停用原因。'
        if u'不通'.encode("utf8") in message_text or u'不能'.encode("utf8") in message_text or u'斷'.encode("utf8") in message_text or u'認證'.encode("utf8") in message_text or u'連'.encode("utf8") in message_text or \
           u'無法'.encode("utf8") in message_text or u'問題'.encode("utf8") in message_text:
            faq = template_json.Template_json(sender_id,template_type=2,
                   text="是否曾申請過帳號呢? (請用是/否按扭回答以便記錄)", payload_yes = "START_STATE_YES", payload_no = "START_STATE_NO" )
            return faq

        return '請參考宿網管理系統FAQ http://dorm.cc.ncku.edu.tw/ '

    if u'資安通報'.encode("utf8") in message_text :
        return '您好  需要填寫資安通報，可以先從 https://goo.gl/YzegaO 這裡下載通報檔案，填寫完後直接回傳至security@mail.ncku.edu.tw 這個信箱，或是繳交紙本到計網中心一樓'

    if len(ip) > 0 :
        # start = message_text.find("ip:")
        # mac_start = message_text.find("mac:")
        # end = 0
        # mac_end = 0
        # if start >= 0 :
        #     for i in range(len(message_text)) :
        #         if i > (start + 4) and message_text[i] == " " : #  first whitespace after "ip:"
        #             end = i
        #             break
        #
        #     for i in range(len(message_text)) :
        #         if i > (mac_start + 4) and message_text[i] == " " : #  first whitespace after "mac:"
        #             mac_end = i
        #             break
        #     ip = message_text[start+3:end]
        #     mac = message_text[mac_start+4:mac_end]
        #     print(ip)
        #     print(mac)

            data = {}
            data['ip'] = unicode(ip[0])
            data['mac'] = u'xx:xx:xx:xx:xx:xx nothing here'
            url_values = urllib.urlencode(data)
            print(url_values)
            full_url = 'https://script.google.com/macros/s/AKfycbwdyCdon5MQYAz-U-WbP-EVgvymqnx5-k9AHDVBd2ZJ1CgShto/exec' + '?' + unicode(url_values)

            response = urllib.urlopen(full_url).read()
            print(response)
            if response == 'found!':
                return '您的網路位置IP被暫停使用 請聯絡計網中心  聯絡方式：（06）2757575 ext.61010'
            else : return '您的網路位置IP不在鎖網名單中，並非被暫停使用，請留下資料將有專人為您服務'



    #授權軟體
   
#=====================================================================


    #選課
    if u'選課'.encode("utf8") in message_text :
        if u'無法'.encode("utf8") in message_text or u'忘'.encode("utf8") in message_text or u'登'.encode("utf8") in message_text :
            return '您好  選課系統與成功入口帳號密碼是一樣的，請先試登入成功入口到右上方設定做密碼變更，若成功入口也沒有辦法登入，則需要修改成功入口密碼,請攜帶雙證件(學生證以及身分證)於上班時間到計算機中心一樓服務台,做更改密碼之服務。'

    #moodle
    if u'moodle'.encode("utf8") in message_text :
        if u'無法'.encode("utf8") in message_text or u'忘'.encode("utf8") in message_text or u'登'.encode("utf8") in message_text :
            return '您好  moodle系統與成功入口帳號密碼是一樣的，請先試登入成功入口到右上方設定做密碼變更，若成功入口也沒有辦法登入，則需要修改成功入口密碼,請攜帶雙證件(學生證以及身分證)於上班時間到計算機中心一樓服務台,做更改密碼之服務。'


    #成功入口
    if u'成功入口'.encode("utf8") in message_text :
        if u'改'.encode("utf8") in message_text or u'無法'.encode("utf8") in message_text or u'忘'.encode("utf8") in message_text or u'登'.encode("utf8") in message_text :
            return '您好  若您是在校學生:若需要修改成功入口密碼,請攜帶雙證件(學生證以及身分證)於上班時間到計算機中心一樓服務台,做更改密碼之服務。\n若您已是畢業生:成功入口僅服務在校學生，故學生畢業後，成功入口帳號即停用。'

    #mybox
    if 'mybox' in message_text :
        return '您好  若無法連結mybox，可能是mybox帳號尚未開通，請先到mybox系統 (http://mybox.ncku.edu.tw) 啟用你的mybox帳號'

    #畢業
    if u'畢業'.encode("utf8") in message_text :
        return '您好  成功入口僅服務在校學生，故學生畢業後，成功入口帳號即停用。個人mail帳號，則於畢業6個月後停用，而E-portfolio數位學習歷程檔可由該系統原網址登入使用。'

    #成績
    if u'成績'.encode("utf8") in message_text :
        return '您好  請由成功入口進去後，E-portfolio數位學習歷程檔裡就有成績查詢的選項 ， 或由註冊組網頁連到成績查詢網頁。( 註冊組 -> 線上服務 -> 學生 -> 成績查詢 )'


    #閒聊  字數不能太多

def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message":{
            "attachment":{
                "type":"template",
                "payload":{
                    "template_type":"button",
                    "text": message_text ,
                    "buttons":[
                        {
                            "type":"postback",
                            "title":"不是我要的答案",
                            "payload":"不是我要的答案"
                        }
                        ]
                }
            }
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)

def send_template_message(reply):
    data = json.dumps(reply.template)
    sendtofb(data)


def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()


if __name__ == '__main__':
    app.run(debug=True)
