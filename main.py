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
                    message_text = messaging_event["message"]["text"]  # the message's text

                    if sender_id != os.environ["SOCIAL_CHAIR_BOT"]:
                        response = get_events_in_area(sender_id, message_text)
                    else:
                        response = 'something else'

                    send_message(sender_id, response)
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
    events = api.call('/events/search', l=location)

    first_name = get_user_details(sender_id)

    log('location: ' + location + '; first_name: ' + first_name)

    # if events['total_items'] == 0:
    #     resposne =  'Sorry ' + first_name + ', nothing came up with that location. Please try again.'
    # else:
    #     respone =  first_name + ', I see ' + events['events']['event'][0]['title'] + ' at ' + events['events']['event'][0]['venue_name']
    response = 'Sorry ' + first_name + ', nothing came up with that location. Please try again.'
    return response

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

def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()

if __name__ == '__main__':
    main.run(debug=True)
