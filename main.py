import sys
import os
import json
import eventful
import facebook

import requests
from flask import Flask, request

main = Flask(__name__)

graph = facebook.GraphAPI(access_token=os.environ["PAGE_ACCESS_TOKEN"],
                            version='2.2')

'''
TODO: same as above but with max(5, total_number of events)
TODO: error check to make sure each has a picture, url, etc.
TODO: use Yahoo Weather's method of confirming location before sending it to API
TODO: create method to update greeting
'''

GREETING = "Hello! Social Chair, at your service. Tell me what city you are in, and I will tell you what is going on this weekend."

@main.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200

@main.route('/', methods=['POST'])
def webhook():
    # endpoint for processing incoming messaging events
    data = request.get_json()
    # log(data)  # you may not want to log every incoming message in production, but it's good for testing

    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):  # someone sent us a message
                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    try:
                        message_text = messaging_event["message"]["text"]  # the message's text
                        if sender_id != os.environ["SOCIAL_CHAIR_BOT"]:
                            get_events_in_area(sender_id, message_text)
                    except KeyError:
                        log('not text receives')

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass
                if messaging_event.get("optin"):  # optin confirmation
                    pass
                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass
    return "ok", 200

def get_user_details(sender_id):
    profile = graph.get_object(sender_id)
    message = profile['first_name']
    return message

def get_events_in_area(sender_id, location):
    api = eventful.API(os.environ["EVENTFUL_TOKEN"])
    events = api.call('/events/search', t='This Weekend', l=location)

    first_name = get_user_details(sender_id)

    if events['total_items'] == '0':
        response =  'Sorry ' + first_name + ', nothing came up with that location. Please try again.'
        send_message(sender_id, response)
    else:
        response =  first_name + ', looks like there are ' + str(events['total_items']) + ' total events going on this weekend. Here are a few:'
        send_message(sender_id, response)
        # response =  'The first listed event is ' + events['events']['event'][0]['title'] + ' at ' + events['events']['event'][0]['venue_name'] + '.'
        send_generic_message(sender_id, events['events']['event'])

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
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    # if r.status_code != 200:
    #     log(r.status_code)
    #     log(r.text)

def send_generic_message(recipient_id, events):
    log("sending generic message to {recipient}".format(recipient=recipient_id))

    list_of_cards = []
    number_of_cards = 3 # min(3, int(events['total_items']))
    for i in range(number_of_cards):
        card = [{
            "title":events[i]['title'],
            "subtitle":events[i]['venue_name'],
            # "item_url":"https://eventful.com",
            "buttons": [{
                "type":"web_url",
                "url":events[i]['url'],
                "title":"View Event Page"}]
        }]
        if 'image' in events[i]:
            if 'medium' in events[i]['image']
                card[0]['image_url'] = events[i]['image']['medium']['url']
        list_of_cards += card

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
        "message": {
            "attachment": {
                "type":"template",
                "payload": {
                    "template_type":"generic",
                    "elements": list_of_cards
                }
            }
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)

def set_greeting():
    log("set greeting: {text}".format(text=GREETING))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "setting_type":"greeting",
        "greeting": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/thread_settings", params=params, headers=headers, data=data)

def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()

if __name__ == '__main__':
    set_greeting()
    main.run(debug=True)
