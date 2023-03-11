"""
_________________________________
OPENASSIGNMENT
__________________________________
"""

import flask
import flask_cors
import pymongo
import os
import traceback
import dotenv
import urllib.parse
import dotenv
import requests
import openai
import random_utilities
import random_utilities.models.time_created
import random


from twilio.rest import Client
from models.response import Response
from models.user import User
from models.conversation import Conversation
from models.message import Message


dotenv.load_dotenv()
openai.api_key = os.environ["OPENAI_API_KEY"]

"""
__________________________________
DEVELOPMENTAL ENVIRONMENT VARIABLES
__________________________________
"""
if os.environ.get("environment") != "production":
	dotenv.load_dotenv()


"""
__________________________________
SERVER INSTANCE SETUP
__________________________________
"""
server_instance = flask.Flask(__name__,
			static_folder="./assets/",
            static_url_path="/server_name/assets/")
flask_cors.CORS(server_instance, resources={r"*": {"origins": "*"}})

"""
__________________________________
DATABASE CONNECTION
__________________________________
"""
users, is_mongo_connected = random_utilities.initiate_mongodb_connection(
	mongo_host=os.environ["MONGODB_HOST"],
	database_name=os.environ["DATABASE_NAME"],
	collection_name="users"
)
random_utilities.log(f"Is MongoDB connected?: {is_mongo_connected}")


""""
____________________________________________
UTILITIES FUNCTIONS
____________________________________________
"""
# A Twilio client that will be used to respond to prompts.
twilio_client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
def send_response_message(to, body, media = None):
	message = twilio_client.messages.create(
		from_=os.environ["TWILIO_PHONENUMBER"],
		body=body,
		media_url=media if media is not None else [],
		to=to
	)

	return message

# Requests a response from the user's request prompt to: https://api.openai.com/v1/chat/completions
models = openai.Model.list()
def request_chatgpt_response(messages):
	# Request data to be made with the request.
	request_data = {"model": "gpt-3.5-turbo",
					"messages": messages, 
					"temperature": random.randrange(0, 1) }
	
	random_utilities.log(f"Using temperature: {request_data['temperature']}.")
	
	# Send the request to the OpenAI API server.
	request_response = requests.post("https://api.openai.com/v1/chat/completions",
				  					json=request_data,
									headers={"Authorization": f"Bearer {openai.api_key}"})

	# Parse the response and relay / return the response
	if request_response.status_code == 200:
		response = request_response.json()["choices"][0]["message"]["content"]
		return response
	else:
		print(request_response.json())
		return "Something went wrong while generating your response, please resend your message."


# Calculates the amount of funds required from the user to generate a response.
def calculate_required_usage(prompt: str):
	tokens_used = float(len(prompt)) / 0.75
	amount_per_token = 0.002
	
	return tokens_used * amount_per_token

RESPONSE_MESSAGES = {
	"MENU": "Here's available menu options:\n\n 1. Balance.\n2. Topup.\n3. About\n4. Terms of usage / usage.",
	"FEEDBACK": "I'd love to hear what you think, do tell me: Use format \"Feedback: <feedback content here>\" to send your feedback to us.",
	"ABOUT": "I'm *OpenAssignment*, a smart assistant designed to assist you with *academic assignments* and *school work*. You can ask me anything and I'll do my best to answer you. \n Courtesy of *Towards Common Foundry, Limited*. Visit *(towardscommonfoundry.com)* for more information.",
	"TOPUP": "To topup your OpenAssignment account follow this link to make a deposit with your card, *use your WhatsApp phone number as reference*: *https://pay.yoco.com/towards-common-foundry*.",
	"NO_BALANCE": "You don't have enough funds for this request."
}



"""
__________________________________
SERVER INSTANCE ROUTES
__________________________________
"""
# Returns status of the server
@server_instance.route("/openassignment/recieve", methods=["POST"])
@flask_cors.cross_origin()
def recieve_prompt():
	try:
		# Read the data and convert it from binary to ASCII.
		request_data = flask.request.get_data().decode("ascii")
		if request_data:
			
			# Data comes in as Query String, convert it to a dictionary
			parsed_data = urllib.parse.parse_qs(request_data)

			# Extract important data points from the parsed_data
			extracted_data_points = dict(
				whatsapp_id=parsed_data["WaId"][0],
				profile_name=parsed_data["ProfileName"][0],
				body=parsed_data["Body"][0],
				from_=parsed_data["From"][0]
			)

			# Check if an already saved user exists in the database.
			user = users.find_one({ "whatsapp_id": extracted_data_points["whatsapp_id"] })
			if not user:
				user = User(extracted_data_points).__dict__
				users.insert_one( user )

			# TODO: deplete the available funds, done
			required_usage = calculate_required_usage(extracted_data_points["body"])
			random_utilities.log(f"Prompt requires: ${required_usage}")
			available_funds_after_prompt = 0 if user["available_funds"] == 0 else user["available_funds"] - required_usage
			
			if available_funds_after_prompt <= 0:
				send_response_message(extracted_data_points["from_"], f"{RESPONSE_MESSAGES['NO_BALANCE']} {RESPONSE_MESSAGES['TOPUP']}")
				return Response(cd=200).to_json()
			
			# Check if the request has a special ask such as: Balance, Quit, Feedback, Menu, Topup, Help, More.
			available_options = ("menu", "menu.", "balance", "balance.", "topup", "topup.", "about", "about.", "terms of usage", "terms of usage.", "usage", "usage.")
			if extracted_data_points["body"].lower() in available_options:
				if extracted_data_points["body"] in ["menu", "menu."]:
					return send_response_message(extracted_data_points["from_"], f"Hello {extracted_data_points['from_']}.\n\n {RESPONSE_MESSAGES['MENU']}")
				elif extracted_data_points["body"] in ["balance", "balance.", "feedback", "feedback."]:
					return send_response_message(extracted_data_points["from_"], f"Your OpenAssignment balance is: R{user['available_funds']}.")
				elif extracted_data_points["body"] in ["topup", "topup."]:
					return send_response_message(extracted_data_points["from_"], RESPONSE_MESSAGES["TOPUP"])
				elif extracted_data_points["body"] in ["terms of usage", "terms of usage.", "usage", "usage."]:
					return send_response_message(extracted_data_points["from_"], RESPONSE_MESSAGES["ABOUT"])
				elif extracted_data_points["body"] in ["feedback", "feedback."]:
					return send_response_message(extracted_data_points["from_"], RESPONSE_MESSAGES["FEEDBACK"])
				else:
					return send_response_message(extracted_data_points["from_"], RESPONSE_MESSAGES["ABOUT"])

			
			# Check if a new conversation is requied
			current_day = random_utilities.models.time_created.TimeCreatedModel().day
			is_create_new_conversation = True if ("Hi" in extracted_data_points["body"]) else False
			
			if is_create_new_conversation or len(user["conversations"]) == 0:
				# Make a new conversation
				conversation = Conversation(dict(messages=[{"content": "Your name is *OpenAssignment*, a *smart assignment assistant*, developed by *Libby Lebyane* sourced from OpenAI: Your're helpful and can assist with theoretical questions.", "role": "system"}])).__dict__
				user["conversations"].append(conversation)
				send_response_message(extracted_data_points["from_"], f"Hello {extracted_data_points['from_']}.\n\n {RESPONSE_MESSAGES['MENU']}.\n\nCourtesy of *Towards Common Foundry, Limited*. Visit *(towardscommonfoundry.com)* for more information.", media=["https://storage.googleapis.com/hetchfund_files_bucket/support%40towardscommonfoundry.com/f8ab1c6c-ad02-4191-acf9-0104cd9c3e7c.png"])

			# Make a request message wrapper
			request_message = Message(dict(role="user", content=extracted_data_points["body"])).__dict__

			# Add the request message to the conversation
			print(user["conversations"][len(user["conversations"]) - 1])
			user["conversations"][len(user["conversations"]) - 1]["messages"].append(request_message)

			# # Generate the response from the list of conversations.
			gpt_response = request_chatgpt_response(user["conversations"][len(user["conversations"]) - 1]["messages"])
			request_response = Message(dict(role="assistant", content=gpt_response)).__dict__

			# Add the response to the records as well.
			user["conversations"][len(user["conversations"]) - 1]["messages"].append(request_response)

			
			
	
			# Update the database records for the user conversations
			user["available_funds"] -= required_usage # Deplete the amount.
			users.update_one({ "whatsapp_id": extracted_data_points["whatsapp_id"] },
		    	{
					"$set": {
						**user
					}
				})


			# # Respond to the user.
			message = send_response_message(extracted_data_points["from_"], gpt_response)
			if message:
				return Response(cd=200, rs="Ok").to_json()
			else:
				return Response(cd=500, rs="Something went wrong.").to_json()
		
		else:
			return Response(cd=400, rs="Something went wrong.").to_json()
	except:
		print(traceback.format_exc())
		return Response(cd=500, rs="Something went wrong.").to_json()
