# basic packages
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import random, time, os
from datetime import datetime, timedelta
from random import randint
import json
from io import StringIO
from typing import Dict, Any, Optional
import configparser
import re
from datetime import datetime

# importing helper functions
from utils import *
from logger_config import logger


def generate_error_response(error_message, error_type=None):
    final_output = {}
    if error_type == "user_query":
        final_output["response"] = "Sorry, can you please provide query"
    else:
        final_output[
            "response"
        ] = "Sorry, I didn't quite understand your request. Could you please provide more details or clarify your question"

    final_output["pretype_prompts"] = [
        "Who is Y-Axis?",
        "What are the services offered by Y-Axis?",
        "Why should I choose Y-Axis?",
    ]
    final_output["error_message"] = error_message
    return final_output


def lambda_handler(event, context) -> dict:
    """
    AWS Lambda handler to handle user queries for Y-axis.

    Args:
        event (Dict): Event data from the AWS Lambda trigger.
        context (Optional): Context object with runtime information.

    Returns:
        dict: Dictionary containing the status code and result message.
    """
    try:
        # Extract user query and session id from event dict
        user_query = event["user_query"]
        session_id = event["session_id"]

        # clean user query
        user_query = clean_user_query(user_query)

        # checking whether user query is none or not
        if user_query is None or len(user_query.strip()) < 1:
            error_message = "user query is empty"
            logger.info(error_message)
            final_output = generate_error_response(error_message, "user_query")
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        logger.info(f"session id is {session_id}")
        logger.info(f"user query is {user_query}")

        # extract salesforce details from secrets manager
        secret_name = os.environ["secret_name"]
        secret_region_name = os.environ["secret_region_name"]

        salesforce_secret = get_secret(secret_name, secret_region_name)

        # checking if salesforce secret is none or not
        if salesforce_secret is None:
            error_message = "Error in getting salesforce secrets from secret manager"
            logger.info(error_message)
            final_output = generate_error_response(error_message, "salesforce_secret")
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        # Access salesforce secret values
        username = salesforce_secret.get("user_name")
        password = salesforce_secret.get("password")
        security_token = salesforce_secret.get("security_token")
        domain = salesforce_secret.get("domain")

        # extract bedrock model id and dynamoDB tables
        model_id = os.environ["model_id"]
        chat_history_table = os.environ["chat_history_table"]
        leads_table_name = os.environ["leads_table_name"]

        # extract region names
        bedrock_region_name = os.environ["bedrock_region_name"]
        dynamodb_region_name = os.environ["dynamodb_region_name"]

        # extract guardrail id and version
        guardrail_id = os.environ["guardrail_id"]
        guardrail_version = os.environ["guardrail_version"]

        # getting bedrock client
        bedrock_runtime = get_bedrock_client(bedrock_region_name)

        if bedrock_runtime is None:
            error_message = "Error in creating bedrock runtime"
            logger.info(error_message)
            final_output = generate_error_response(error_message, "bedrock_runtime")
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        # get dynamodb client
        dynamodb_client = get_dynamodb_client(dynamodb_region_name)

        if dynamodb_client is None:
            error_message = "Error in creating dynamodb client"
            logger.info(error_message)
            final_output = generate_error_response(error_message, "dynamodb_client")
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        # loading system prompt
        with open("prompts/system_instructions.txt") as f:
            system_prompt = f.read()

        # get chat history
        chat_history = get_session_history(
            session_id, chat_history_table, dynamodb_client
        )

        if chat_history is None:
            error_message = "Error in getting chat history"
            logger.info(error_message)
            final_output = generate_error_response(error_message, "chat_history")
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        logger.info(f"length of chat_history is {len(chat_history)}")

        # create conversation message.
        conversation = [{"role": "user", "content": [{"text": user_query}],}]

        chat_history = chat_history + conversation

        # getting response for user query
        attempt_limit = 2
        attempts = 0
        while attempts < attempt_limit:
            model_response_text, model_response_dict = get_bedrockchat_model_response(
                system_prompt,
                chat_history,
                bedrock_runtime,
                model_id,
                guardrail_id,
                guardrail_version,
            )
            logger.info(f"model_response for user query is {model_response_text}")
            if model_response_text is not None:
                break
            attempts = attempts + 1

        if model_response_text is None:
            final_output = {}
            error_message = "error in getting model response"
            logger.info(error_message)
            final_output = generate_error_response(error_message, "model_response_text")
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        # Updating the chat history
        if len(chat_history) == 1:
            chat_history.append(model_response_dict)
            logger.info("inserting new session id")
            insert_session_history(
                session_id, chat_history, chat_history_table, dynamodb_client
            )
        else:
            chat_history.append(model_response_dict)
            update_session_history(
                session_id, chat_history_table, chat_history, dynamodb_client
            )
            logger.info("updating existing session history")

        # get pretyped prompts
        pretype_prompts_list = get_pretyped_prompts(
            model_response_text, system_prompt, bedrock_runtime, model_id
        )
        logger.info(f"pretype_prompts_list is {pretype_prompts_list}")

        final_output = {}
        final_output["response"] = model_response_text
        final_output["pretype_prompts"] = pretype_prompts_list
        logger.info(f"lambda response is {final_output}")
        return {
            "statusCode": 200,
            "body": json.dumps(final_output),
        }

    except Exception as e:
        # Handle and log any exceptions
        error_message = f"An error occurred: {e}"
        logger.error(error_message)
        final_output = generate_error_response(error_message, "other_errors")
        logger.info(f"lambda response is {final_output}")
        return {"statusCode": 500, "body": json.dumps(final_output)}
