# basic packages
import boto3
from typing import Dict
import random, time, os
from datetime import datetime, timedelta
from random import randint
import json
from dotenv import load_dotenv
from io import StringIO
from typing import Dict, Any, Optional
import configparser
import re

# salesforce packages
from simple_salesforce import (
    Salesforce,
    SalesforceMalformedRequest,
    SalesforceResourceNotFound,
)

# logging
from logger_config import logger

from validate_user_details import ValidateUserDetails


def get_secret(secret_name, region_name):
    try:
        # Create a Secrets Manager client
        client = boto3.client("secretsmanager", region_name=region_name)

        # Retrieve the secret value
        response = client.get_secret_value(SecretId=secret_name)

        # Parse and return the secret
        if "SecretString" in response:
            secret_data = response["SecretString"]
        else:
            secret_data = base64.b64decode(response["SecretBinary"])

        return json.loads(secret_data)

    except Exception as e:
        logger.error(f"Error retrieving secret: {e}")
        return None


# Convert 'lead_updated_at' to a proper datetime object
def is_recent_lead(lead_updated_at, hours_filter):
    try:
        # Assuming 'lead_updated_at' is in the format '2024-10-03 13:31:21.824414'
        updated_at = datetime.strptime(lead_updated_at, "%Y-%m-%d %H:%M:%S.%f")

        # Get the current time and check if the lead was updated in the last 48 hours
        now = datetime.now()
        time_difference = now - updated_at

        return time_difference <= timedelta(hours=hours_filter)

    except Exception as e:
        logger.info(f"Error parsing date: {e}")
        return False


# Extract session IDs where 'lead_updated_at' is within the last 48 hours
def extract_recent_session_ids(dynamodb_client, leads_table, hours_filter):
    try:
        table = dynamodb_client.Table(leads_table)
        # Scan the table and get all items
        response = table.scan()

        # Filter out session IDs updated in the last 48 hours
        recent_session_ids = [
            item["session_id"]
            for item in response["Items"]
            if (is_recent_lead(item.get("lead_updated_at"), hours_filter))
            and (item.get("lead_id") != "None")
        ]
        return recent_session_ids
    except Exception as e:
        logger.info(f"Error extracting recent session IDs: {e}")
        return None


# Convert 'lead_updated_at' to a proper datetime object
def is_recent_chat_history(
    dynamodb_client, chat_history_table_name, session_id, hours_filter
):
    try:
        table = dynamodb_client.Table(chat_history_table_name)
        response = table.get_item(Key={"session_id": session_id})
        last_updated_at = response["Item"]["updated_at"]

        # Assuming 'lead_updated_at' is in the format '2024-10-03 13:31:21.824414'
        updated_at = datetime.strptime(last_updated_at, "%Y-%m-%d %H:%M:%S.%f")

        # Get the current time and check if the lead was updated in the last 48 hours
        now = datetime.now()
        time_difference = now - updated_at

        return time_difference <= timedelta(hours=hours_filter)
    except Exception as e:
        logger.info(f"Error at checking whether recent chat history or not: {e}")
        return False


def retrieve_previous_user_info(dynamodb_client, leads_table, session_id):
    try:
        table = dynamodb_client.Table(leads_table)
        response = table.get_item(Key={"session_id": session_id})
        previous_user_data = response["Item"]["user_details"]
        lead_id = response["Item"]["lead_id"]
        previous_user_inputs = response["Item"]["user_inputs"]
        lead_update_attempts = response["Item"]["lead_update_attempts"]
        return previous_user_data, lead_id, previous_user_inputs, lead_update_attempts
    except Exception as e:
        logger.info(f"Error in getting previous user data: {e}")
        return None, None, None, 0


def find_updated_list_with_values(list_old, list_new):
    try:
        updated_list = list(set(list_new) - set(list_old))
        return updated_list
    except Exception as e:
        logger.info(f"Error in getting updated list values: {e}")
        return {}


def find_updated_keys_with_values(dict_old, dict_current):
    try:
        # Find the keys where the values in dict_B are different from dict_A and get the new values
        updated_dict = {
            key: dict_current[key]
            for key in dict_current
            if dict_old.get(key) != dict_current.get(key)
        }
        return updated_dict
    except Exception as e:
        logger.info(f"Error in getting updated dict values: {e}")
        return {}


# Function to get session ids and summaries for a particular lead_id
def get_summaries_for_lead(lead_id, current_session_id, dynamodb_client, leads_table):
    try:
        table = dynamodb_client.Table(leads_table)
        # Query to retrieve all rows for the given lead_id
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr("lead_id").eq(lead_id)
        )

        if len(response["Items"]) > 1:
            # Sort the items by 'lead_updated_at' in descending order (most recent first)
            sorted_items = sorted(
                response["Items"],
                key=lambda x: datetime.strptime(
                    x.get("lead_updated_at"), "%Y-%m-%d %H:%M:%S.%f"
                ),  # Adjusted for fractional seconds
                reverse=True,
            )

            count = 0  # Initialize count variable to store only last 5 summaries
            
            # Extract session_ids and summaries
            session_summaries = []
            for item in sorted_items:
                session_id = item.get("session_id")
                if session_id != current_session_id:
                    print(f"session_id is {session_id}")
                    summary = item.get("summary")
                    count += 1  # Increment count
                    if summary:
                        session_summaries.append(summary)
                    if count > 5:  # Break out of loop if count exceeds 4
                        break

            # Join all summaries together
            joined_summary = "\n\n".join(session_summaries)
        else:
            joined_summary = ""

        return joined_summary
    except Exception as e:
        logger.info(
            f"Error in getting the summary for the all session ids of a lead id: {e}"
        )
        return ""


def update_lead_id(salesforce_object, lead_id, user_details_dict, summary, session_id, dynamodb_client, leads_table):
    try:
        existing_summary = get_summaries_for_lead(lead_id, session_id, dynamodb_client, leads_table)
        new_summary = summary + "\n\n" + existing_summary
        user_details_dict["Description"] = new_summary
        # update the lead
        update_response = salesforce_object.Lead.update(lead_id, user_details_dict)

        # Handle the 204 response (successful update)
        if update_response == 204:
            logger.info(f"Lead {lead_id} updated successfully")
            return True
        else:
            return False
    except Exception as e:
        logger.info(f"Error in updating the lead: {e}")
        return False


def update_leads_table(
    dynamodb_client,
    leads_table,
    session_id,
    user_details_dict,
    summary,
    user_inputs,
    lead_update_attempts,
):
    try:
        table = dynamodb_client.Table(leads_table)
        table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET user_details = :updated_user_details, lead_updated_at = :new_timestamp,summary = :new_summary,user_inputs = :new_user_inputs, lead_update_attempts = :new_lead_update_attempts",
            ExpressionAttributeValues={
                ":updated_user_details": user_details_dict,
                ":new_timestamp": str(datetime.utcnow()),
                ":new_summary": summary,
                ":new_user_inputs": user_inputs,
                ":new_lead_update_attempts": lead_update_attempts,
            },
        )
        return True
    except Exception as e:
        logger.info(f"Error in updating leads table: {e}")
        return False


def clean_user_query(query):
    try:
        # Remove multiple spaces
        cleaned_query = re.sub(r"\s+", " ", query)

        # Strip leading and trailing spaces
        cleaned_query = cleaned_query.strip()

        return cleaned_query

    except Exception as e:
        print(f"An error occurred: {e}")
        return query


# Initialize Bedrock client
def get_bedrock_client(region_name):
    try:
        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime", region_name=region_name,
        )
        return bedrock_runtime
    except Exception as e:
        logger.error(f"Failed to set up Bedrock client: {e}")
        return None


def get_dynamodb_client(region_name):
    try:
        # Initialize the DynamoDB resource
        dynamodb_client = boto3.resource("dynamodb", region_name=region_name)
        return dynamodb_client
    except Exception as e:
        logger.error(f"Failed to set up DynamoDB client: {e}")
        return None


def get_bedrockchat_model_response(
    system_prompt,
    chat_history,
    bedrock_runtime,
    model_id,
    guardrail_id,
    guardrail_version,
):
    try:
        # System prompts.
        system_prompts = [{"text": system_prompt}]

        # inference parameters to use.
        temperature = 0.5
        top_k = 200
        topP = 0.9
        maxTokens = 4096

        # Base inference parameters.
        inference_config = {
            "temperature": temperature,
            "maxTokens": maxTokens,
            "topP": topP,
        }

        # Additional model inference parameters.
        additional_model_fields = {"top_k": top_k}

        # Configuration for the guardrail.
        guardrail_config = {
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion": guardrail_version,
            "trace": "enabled",
        }

        # Send the message to the model, using a basic inference configuration.
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=chat_history[-31:],
            system=system_prompts,
            inferenceConfig=inference_config,
            additionalModelRequestFields=additional_model_fields,
            guardrailConfig=guardrail_config,
        )

        logger.info(
            f"model response parameters for generating response to user query is {response}"
        )

        # Extract and print the response text.
        model_response_text = response["output"]["message"]["content"][0]["text"]
        model_response_dict = response["output"]["message"]
        return model_response_text, model_response_dict
    except Exception as e:
        logger.info(f"Exception {e} occured while getting response for user query")
        return None, None


# Step 3: Get history based on session_id (returns empty list if session_id not found)
def get_session_history(session_id, table_name, dynamodb_client):
    try:
        table = dynamodb_client.Table(table_name)
        response = table.get_item(Key={"session_id": session_id})

        if "Item" in response:
            return response["Item"]["history"]
        else:
            return []
    except Exception as e:
        logger.info(f"Exception {e} occured while getting chat history")
        return None


# Step 2: Insert new values (session_id, history)
def insert_session_history(session_id, history, table_name, dynamodb_client):
    try:
        table = dynamodb_client.Table(table_name)
        current_time = str(datetime.utcnow())
        table.put_item(
            Item={
                "session_id": session_id,
                "history": history,
                "created_at": current_time,
                "updated_at": current_time,
            }
        )
        logger.info(f"Inserted new session id chat history")
    except Exception as e:
        logger.info(f"Exception {e} occured while insert chat history")


# Step 4: Update the history column for a given session_id
def update_session_history(session_id, table_name, chat_history, dynamodb_client):
    try:
        table = dynamodb_client.Table(table_name)

        # Update the table with the new history
        table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET history = :new_history, updated_at = :new_timestamp",
            ExpressionAttributeValues={
                ":new_history": chat_history,
                ":new_timestamp": str(datetime.utcnow()),
            },
        )
        logger.info(f"Updated history for session {session_id} successfully.")
    except Exception as e:
        logger.info(f"Exception {e} occured while updating chat history")


def extract_user_details(
    user_inputs, user_details_extraction_prompt, model_id, bedrock_runtime
):
    try:
        join_user_inputs = ".\n ".join(user_inputs)

        # modify the prompt
        new_prompt = user_details_extraction_prompt.replace(
            "{input_query}", join_user_inputs
        )

        body = {}
        body["anthropic_version"] = "bedrock-2023-05-31"
        body["max_tokens"] = 10000
        body["messages"] = [{"role": "user", "content": new_prompt}]

        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )

        logger.info(
            f"model response parameters for extracting user details is {response}"
        )

        # Parse the response
        response_body = json.loads(response["body"].read().decode("utf-8"))
        user_details = response_body["content"][0]["text"].strip()
        return user_details
    except Exception as e:
        logger.info(f"Exception {e} occured while extracting user details")
        return None


def parse_user_details(user_details):
    pairs = user_details.split(",")
    pairs = [item.replace("\n", "") for item in pairs]

    # Loop through each pair
    user_info_dict = {}
    for pair in pairs:
        # Split the pair into key and value
        if ": " in pair:
            key, value = pair.split(": ", 1)
            key = key.strip()
            value = value.strip()
            user_info_dict[key] = value

    return user_info_dict


def validate_user_info(user_details_dict):
    validate_user_details_obj = ValidateUserDetails()

    # Name validation
    name = user_details_dict.get("Name", "None")
    print(f"name is {name}")
    if validate_user_details_obj.check_name(name):
        name_parts = name.split()
        if len(name_parts) > 1:
            user_details_dict["first_name"] = name_parts[0]
            user_details_dict["last_name"] = name_parts[-1]
        else:
            user_details_dict["first_name"] = name_parts[0]
            user_details_dict["last_name"] = None
    else:
        user_details_dict["first_name"] = None
        user_details_dict["last_name"] = None

    # removing Name key as it is no longer needed
    removed_value = user_details_dict.pop("Name", None)

    # Age validation
    age = user_details_dict.get("Age", "None")
    print(f"age is {age}")
    if age.isdigit() and validate_user_details_obj.check_age(age):
        user_details_dict["Age"] = int(age)
    else:
        user_details_dict["Age"] = None

    # Email validation
    email = user_details_dict.get("Email", "None")
    print(f"Email is {email}")
    if validate_user_details_obj.check_email(email):
        user_details_dict["Email"] = email
    else:
        user_details_dict["Email"] = None

    # Country code validation
    country_code = user_details_dict.get("Country Code", "None")
    print(f"Country Code is {country_code}")
    if validate_user_details_obj.check_country_code(country_code):
        user_details_dict["Country Code"] = country_code
    else:
        user_details_dict["Country Code"] = None

    # Phone number validation
    phone = user_details_dict.get("Phone", "None")
    print(f"Phone number is {phone}")
    if validate_user_details_obj.check_phone(phone):
        user_details_dict["Phone"] = phone
    else:
        user_details_dict["Phone"] = None

    # Prepare the final data
    user_details_dict = {
        "FirstName": user_details_dict.get("first_name", "None")
        if user_details_dict.get("first_name", "None") != "None"
        else "Not specified",
        "LastName": user_details_dict.get("last_name", "None")
        if user_details_dict.get("last_name", "None") != "None"
        else "Not specified",
        "Age1__c": user_details_dict.get("Age", "None")
        if user_details_dict.get("Age", "None") != "None"
        else " ",
        "Marital_Status__c": user_details_dict.get("Marital Status", "None")
        if user_details_dict.get("Marital Status", "None") != "None"
        else "Not specified",
        "Work_Experience__c": user_details_dict.get("Work Experience", "None")
        if user_details_dict.get("Work Experience", "None") != "None"
        else "Not specified",
        "What_is_your_highest_education__c": user_details_dict.get(
            "Highest Qualification", "None"
        )
        if user_details_dict.get("Highest Qualification", "None") != "None"
        else " ",
        "Nationality__c": user_details_dict.get("Citizen", "None")
        if user_details_dict.get("Citizen", "None") != "None"
        else "Not specified",
        "Visa_Status__c": user_details_dict.get("Visa Status", "None")
        if user_details_dict.get("Visa Status", "None") != "None"
        else "Not specified",
        "Domicile_Country__c": user_details_dict.get("Current Location", "None")
        if user_details_dict.get("Current Location", "None") != "None"
        else "Not specified",
        "Where__c": user_details_dict.get("Future Location", "None")
        if user_details_dict.get("Future Location", "None") != "None"
        else "Not specified",
        "Specialization__c": user_details_dict.get("Subject", "None")
        if user_details_dict.get("Subject", "None") != "None"
        else "Not specified",
        "Designation__c": user_details_dict.get("Profession", "None")
        if user_details_dict.get("Profession", "None") != "None"
        else "Not specified",
        "How__c": user_details_dict.get("How", "None")
        if user_details_dict.get("How", "None") != "None"
        else "Not specified",
        "Email": user_details_dict.get("Email", "None")
        if user_details_dict.get("Email", "None") != "None"
        else "Not specified",
        "Phone": user_details_dict.get("Phone", "None")
        if user_details_dict.get("Phone", "None") != "None"
        else "Not specified",
        # 'Country_Code__c': country_code if country_code else 'Not specified',  # Uncomment if needed
        "Prospect_Contact_Details__c": "AI Chatbot",
        "YRN_Source__c": "Website",
        "LeadSource": "Our Website",
    }

    return user_details_dict


def format_conversation_history(chat_history):
    conversation_history_list = []
    for entry in chat_history:
        role = entry["role"]
        text = entry["content"][0]["text"]
        conversation_history_list.append({"role": role, "content": text})

    return conversation_history_list


def generate_conversation_summary(
    conversation_history_list, bedrock_runtime, model_id, summarization_prompt, session_id
):
    if not conversation_history_list:
        return "No conversation history available."

    # Prepare the conversation history
    conversation_text = "\n".join(
        [
            f"{message['role'].capitalize()}: {message['content']}"
            for message in conversation_history_list
        ]
    )
    # modify the prompt
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_prompt = summarization_prompt.replace(
        "{conversation_text}", conversation_text
    ).replace("{current_datetime}", current_datetime).replace("{session_id}", session_id)

    try:
        body = {}
        body["anthropic_version"] = "bedrock-2023-05-31"
        body["max_tokens"] = 10000
        body["messages"] = [{"role": "user", "content": new_prompt}]

        summarization_response = bedrock_runtime.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )

        # Parse the response
        response_body = json.loads(
            summarization_response["body"].read().decode("utf-8")
        )
        summary = response_body["content"][0]["text"].strip()
        return summary
    except Exception as e:
        logger.info(f"Exception {e} occured while getting conversation summary")
        return f"Error generating summary: {e}"


def get_salesforce_object(username, password, security_token, domain):
    try:
        # Set your Salesforce credentials here
        sf = Salesforce(
            username=username,
            password=password,
            security_token=security_token,
            domain=domain,
        )
        return sf
    except Exception as e:
        logger.info(f"Exception {e} occured while creating salesforce object")
        return None