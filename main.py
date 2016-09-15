import sys
import os
import json
import requests
import facebook
import simplejson
import apiai

import requests
from flask import Flask, request

main = Flask(__name__)

FB_GRAPH_API   = facebook.GraphAPI(access_token=os.environ["PAGE_ACCESS_TOKEN"], version='2.2')
API_AI         = apiai.ApiAI(os.environ["API_AI_TOKEN"])
EVENTFUL_TOKEN = os.environ["EVENTFUL_TOKEN"]

'''
TODO: handle case where no 'entity' or 'location' is given by user. what happens?
TODO: add 4th (or nth) card to is just a link to the website for all queries (i.e. query on cateogry=x, location=y)
TODO: can we change the order or results that come out? --> https://github.com/SurgeClub/research/blob/24995b923b18aacffb6552754871e87b386bdffb/eventful.py
TODO: add option to buy tickts?
TODO: add initial message that explains usage?
TODO: add pictures for events that do not have pictures (graph some stock photos?)
TODO: use Yahoo Weather's method of confirming location before sending it to API
TODO: add more 'entities' to api.ai for use
TODO: have Kracov help update the Facebook Page
'''

GREETING = "Hello! Social Chair here, to help you find things to do this weekend."

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
                            get_events(sender_id, message_text)
                    except KeyError:
                        log('not text receives')
                        log(messaging_event)

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass
                if messaging_event.get("optin"):  # optin confirmation
                    pass
                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass
    return "ok", 200

def get_user_details(sender_id):
    profile = FB_GRAPH_API.get_object(sender_id)
    message = profile['first_name']
    return message

def extract_data(message):
    request = API_AI.text_request()
    request.lang = 'en'
    request.query = message
    answer = request.getresponse()
    data = simplejson.loads(answer.read())
    category = data['result']['parameters']['category-type']
    location = data['result']['parameters']['geo-city']
    return [category, location]

def get_events(sender_id, message):
    information = extract_data(message)

    params = {
        "app_key": EVENTFUL_TOKEN,
        "location": information[1],
        "category": information[0],
        "include": "categories,popularity,tickets,subcategories",
        "page_size": "100",
        "sort_order": "popularity",
        "date": "This Weekend",
    }

    r = requests.get('https://api.eventful.com/json/events/search', params=params)
    events = r.json()
    log('query: ' + message + '; category: ' + information[0] + '; location: ' + information[1])

    if events['total_items'] == '0':
        response =  'Sorry, no events came up. Try again with a different search.'
        send_message(sender_id, response)
    else:
        response =  'Looks like there are ' + str(events['total_items']) + ' total events going on this weekend. Here are a few:'
        send_message(sender_id, response)
        # TODO sleep for a second to let user read the first message
        send_generic_message(sender_id, events['events']['event'], int(events['total_items']), information)

def send_generic_message(recipient_id, events, number_events, information):
    log("sending generic message to {recipient}".format(recipient=recipient_id))

    list_of_cards = []
    number_of_cards = min(3, number_events)
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
            if events[i]['image'] != None and 'medium' in events[i]['image']:
                card[0]['image_url'] = events[i]['image']['medium']['url']
        list_of_cards += card

    log("created the cards for output")

    # card = [{
    #     "title":"All Events",
    #     # "subtitle":events[i]['venue_name'],
    #     # "item_url":"https://eventful.com",
    #     "buttons": [{
    #         "type":"web_url",
    #         "url":"http://eventful.com/events?q=" + information[0] + "&l= " + information[1] + "&t=This+Weekend",
    #         "title":"Full List of Events"}]
    # }]
    # list_of_cards += card

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

    log("send the cards to the user")

def send_message(recipient_id, message_text):
    # log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

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
