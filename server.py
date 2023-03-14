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

	# Log purposes.
	random_utilities.log(f'Message {body[0:20]} sent to: {to}.')

	# Return.
	return Response(cd=200).to_json()

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


"""
Template response messages.
"""
TEMPLATE_RESPONSE_MESSAGES = {
	"DISCLOSURE": "Hello! This *should be used for educational purposes* only. Information curated may *_not be fully accurate_*. Please verify the information *_for more accuracy_*.",
	"AVAILABLE_OPTIONS": '*_Menu_*\n1. *Balance* _("check balance" / "balance" / "available balance")_\n2. *Topup* _("recharge" / "restore" / "topup")_\n3. *About* _("about" / "help")_\n4. *Terminate* _("stop" / "delete account" / "terminate / "exit")_',
	"FEEDBACK": "I'd love to hear what you think, do tell me: Use format \"Feedback: <feedback content here>\" to send your feedback to us.",
	"ABOUT": "I'm *OpenAssignment*, a smart assistant designed to assist you with *academic assignments* and *school work*. You can ask me anything and I'll do my best to answer you.",
	"TOPUP": "To topup your *OpenAssignment* account follow this link to make a deposit with your card, *use your WhatsApp phone number as reference*: *https://pay.yoco.com/towards-common-foundry*.",
	"NO_BALANCE": "You don't have enough funds for this request.",
	"ATTRIBUTION": "Courtesy of *Towards Common Foundry, Limited*. Visit *(towardscommonfoundry.com)* for more information."
}


"""
__________________________________
SERVER INSTANCE ROUTES
__________________________________
"""
# Returns status of the server
@server_instance.route("/openassignment/recieve", methods=["POST"])
@flask_cors.cross_origin()
def recieve_message_prompt():
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
				body=parsed_data["Body"][0].lower(),
				from_=parsed_data["From"][0]
			)

			# Check if an already saved user exists in the database.
			user = users.find_one({ "whatsapp_id": extracted_data_points["whatsapp_id"] })
			if not user:
				# If not create a new one.
				user = User(extracted_data_points).__dict__
				users.insert_one( user )

			balance_required = calculate_required_usage(extracted_data_points["body"])
			balance_available_after_prompt = 0 if user[ "balance" ] == 0 else user[ "balance" ] - balance_required
			if balance_available_after_prompt <= 0:
				send_response_message(extracted_data_points["from_"], f"{TEMPLATE_RESPONSE_MESSAGES['NO_BALANCE']} {TEMPLATE_RESPONSE_MESSAGES['TOPUP']}")
				return Response(cd=200).to_json()
			
			# These are options available to the user for prompts.
			prompt_options = {
				"greetings": ( "hi", "hey", "hello", "good morning", "good afternoon", "good evening" ),
				"balance_options": ( "check balance", "balance", "available balance" ),
				"topup": ( "topup", "recharge", "restore" ),
				"about": ("about", "help"),
				"stop": ( "stop", "delete account", "terminate", "exit" )
			}

			"""The prompt the user sent to the service."""
			prompt = extracted_data_points["body"]
			to = extracted_data_points["from_"]

			"""Check for greeting messages."""
			if prompt in prompt_options["greetings"]:
				send_response_message(to, f"{TEMPLATE_RESPONSE_MESSAGES['DISCLOSURE']}\n\n{TEMPLATE_RESPONSE_MESSAGES['AVAILABLE_OPTIONS']}\n\n{TEMPLATE_RESPONSE_MESSAGES['ATTRIBUTION']}", media=["https://openassignment.herokuapp.com/openassignment/logo.png"])

			"""When user wants to check the balance."""
			if prompt in prompt_options["balance_options"]:
				return send_response_message(to, f"Your available balance is: *_R{'%.2f' % user['balance']}_*")
			elif prompt in prompt_options["topup"]:
				return send_response_message(to, TEMPLATE_RESPONSE_MESSAGES["TOPUP"])
			elif prompt in prompt_options["about"]:
				return send_response_message(to, TEMPLATE_RESPONSE_MESSAGES["ABOUT"])
			elif prompt in prompt_options["stop"]:
				if len(user["messages"]) > 0:
					print(user["messages"][-1]["content"], prompt)
					if user["messages"][-1]["content"] == prompt:
						return send_response_message(to, "Your account has been succesfully terminated.")
				return send_response_message(to, f"*This will terminate your session*. *Respond _\"{prompt}\"_* again to confirm this termination:")

			"""Send the prompt to ChatGPT."""
			request = Message(dict(role="user", content=prompt)).__dict__
			user["messages"].append(request)
			
			response = request_chatgpt_response(user["messages"])
			return send_response_message(to, response)
	except:
		print(traceback.format_exc())
		return Response(cd=500, rs="Something went wrong.").to_json()


@server_instance.route("/openassignment/logo.png", methods=["GET"])
def send_logo():
	return flask.send_file("./logo.png")
