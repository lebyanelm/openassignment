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
import twilio


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
def request_chatgpt_response(messages):
	# Request data to be made with the request.
	request_data = {"model": "gpt-3.5-turbo",
					"messages": messages[len(messages) - 10:], # Focus more on the last 10 messages.
					"temperature": random.randint(0, 100) / 100 }
	
	random_utilities.log(f"Temperature: {request_data['temperature']}.")
	
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
	"DISCLOSURE": "Hello! This *should be used for educational purposes* only. Information curated may *_not be fully accurate_*. Please verify the information *_for more accuracy_*. Say *\"Help\"* anytime for help on instructions.",
	"AVAILABLE_OPTIONS": '*_Options_ (Special commands)*\n\n1. *Balance* _("check balance" / "balance" / "available balance")_\n2. *Topup* _("recharge" / "restore" / "topup")_\n3. *About* _("about" / "help")_\n4. *Terminate* _("stop" / "delete account" / "terminate / "exit")_',
	"FEEDBACK": "I'd love to hear what you think, do tell me: Use format \"Feedback: <feedback content here>\" to send your feedback to us.",
	"ABOUT": "I'm *OpenAssignment*, a smart assistant engineered to assist you with *academic assignments* and *school work*. You can ask me anything and I'll do my best to answer you.",
	"TOPUP": "Tshepo! To topup your *OpenAssignment* account follow this link to make a deposit with your card, *use your WhatsApp phone number as reference*: *https://pay.yoco.com/towards-common-foundry*.",
	"NO_BALANCE": "You don't have enough funds for this request.",
	"ATTRIBUTION": "Courtesy of *Towards Common Foundry, Limited*. Visit *(towardscommonfoundry.com)* for more information.",
	"INSTRUCTIONS": "*Instructions / How-to-Use*\n\n*OpenAssignment* helps you with academic questions, to ask one just say *\"Hi\"* and ask your question, *_eg. How to calculate the gradient of a curve?_ (Verify the information before using it)*\n\nYou can also generate any images from text using *_Imagine: <description>_* prompt, eg. *\"Imagine: An astronaut riding a horse in photorealistic style\"*.",
	"SPACER": "\n\n__________________\n\n"
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
			
			# These are options available to the user for prompts: <No balance required for options>
			prompt_options = {
				"greetings": ( "hi", "hey", "hello", "good morning", "good afternoon", "good evening" ),
				"balance_options": ( "check balance", "balance", "available balance" ),
				"topup": ( "topup", "top up", "recharge", "restore" ),
				"about": ("about", "help"),
				"stop": ( "delete", "stop", "delete account", "terminate", "exit" )
			}

			"""The prompt the user sent to the service."""
			prompt = extracted_data_points["body"]
			to = extracted_data_points["from_"]

			"""Check for greeting messages."""
			if prompt in prompt_options["greetings"]:
				# If this is a new user, send them instructions on how to use the service.
				send_response_message(to, f"{TEMPLATE_RESPONSE_MESSAGES['DISCLOSURE']}{TEMPLATE_RESPONSE_MESSAGES['SPACER']}{TEMPLATE_RESPONSE_MESSAGES['AVAILABLE_OPTIONS']}{TEMPLATE_RESPONSE_MESSAGES['SPACER']}{TEMPLATE_RESPONSE_MESSAGES['INSTRUCTIONS']}{TEMPLATE_RESPONSE_MESSAGES['SPACER']}{TEMPLATE_RESPONSE_MESSAGES['ATTRIBUTION']}", media=["https://openassignment.herokuapp.com/openassignment/logo.png"])

			"""When user wants to check the balance."""
			if prompt in prompt_options["balance_options"]:
				return send_response_message(to, f"Your available balance is: *_R{'%.2f' % user['balance']}_*")

			elif prompt in prompt_options["topup"]:
				return send_response_message(to, TEMPLATE_RESPONSE_MESSAGES["TOPUP"])
				
			elif prompt in prompt_options["about"]:
				return send_response_message(to, f'{TEMPLATE_RESPONSE_MESSAGES["ABOUT"]}{TEMPLATE_RESPONSE_MESSAGES["SPACER"]}{TEMPLATE_RESPONSE_MESSAGES["INSTRUCTIONS"]}{TEMPLATE_RESPONSE_MESSAGES["SPACER"]}{TEMPLATE_RESPONSE_MESSAGES["ATTRIBUTION"]}')
				
			elif prompt in prompt_options["stop"]:
				if len(user["messages"]) > 0:
					print(user["messages"][-1]["content"], prompt)
					if user["messages"][-1]["content"] == prompt:
						users.delete_one({ "whatsapp_id": extracted_data_points["whatsapp_id"] })
						return send_response_message(to, "*_Your account has been succesfully terminated, thank you for your usage._* Send a *_\"Hi\"_* message to be re-registered again.")

				request = Message(dict(role="user", content=prompt)).__dict__
				user["messages"].append(request)

				"""Save the changes made and return response to Twilio."""
				users.update_one({ "whatsapp_id": extracted_data_points["whatsapp_id"] },
					{
						"$set": {
							"messages": user["messages"]
						}
					})
				return send_response_message(to, f"*This will terminate your session*. *Respond _\"{prompt}\"_* again to confirm this termination:")

			# <Requires balance to make a prompt>
			balance_required = calculate_required_usage(extracted_data_points["body"])
			balance_available_after_prompt = 0 if user[ "balance" ] == 0 else user[ "balance" ] - balance_required
			if balance_available_after_prompt <= 0:
				return send_response_message(extracted_data_points["from_"], f"{TEMPLATE_RESPONSE_MESSAGES['NO_BALANCE']}{TEMPLATE_RESPONSE_MESSAGES['SPACER']}{TEMPLATE_RESPONSE_MESSAGES['TOPUP']}")


			# < The actual prompts. >
			if "imagine:" in prompt:
					dale_response = openai.Image.create(prompt=prompt.split(":")[1], n=1, size="1024x1024")

					# Decrement the balance to cost of image generating per 1024x1024
					user["balance"] = user["balance"] - 0.38

					send_response_message(to, "This is image was generated with *DALL-E* by *_OpenAI_*. Read more here https://openai.com/policies/dall-e-api/.", media=[dale_response["data"][0]["url"]])
			else:
				"""Send the prompt to ChatGPT."""
				request = Message(dict(role="user", content=prompt)).__dict__
				user["messages"].append(request)
				
				response = request_chatgpt_response(user["messages"])
				response_message = Message(dict(role="assistant", content=response)).__dict__

				"""Save the response of the Assistant."""
				user["messages"].append(response_message)

				# Decrement the balance
				user["balance"] = user["balance"] - balance_required
				
				send_response_message(to, response)
			
			"""Save the changes made and return response to Twilio."""
			users.update_one({ "whatsapp_id": extracted_data_points["whatsapp_id"] },
				{
					"$set": {**user}
				})
			return Response(cd=200).to_json()
	except twilio.base.exceptions.TwilioRestException as e:
		print(e, 'from system.')
		retry_request = Message(dict(role="user", content=f"{prompt}, summarize it to 120 words.")).__dict__
		user["messages"].append(retry_request)
		second_try_response = request_chatgpt_response(user["messages"])
		send_response_message(to, second_try_response)

		users.update_one({ "whatsapp_id": extracted_data_points["whatsapp_id"] },
			{
				"$set": {**user}
			})
		return Response(cd=200).to_json()
	except:
		print(traceback.format_exc())
		return send_response_message(to, "*Something went wrong when producing the response*, content may be too long / an error occured. Request the message again for a *150 words* response.")


@server_instance.route("/openassignment/sms", methods=['GET', 'POST'])
def incoming_sms():
    """Send a dynamic reply to an incoming text message"""
    # Get the message the user sent our Twilio number
    body = flask.request.values
    print(body)

    return str("Ok")


@server_instance.route("/openassignment/logo.png", methods=["GET"])
def send_logo():
	return flask.send_file("./logo.png")
