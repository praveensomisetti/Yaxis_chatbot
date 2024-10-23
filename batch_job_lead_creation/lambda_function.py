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

# salesforce packages
from simple_salesforce import (
    Salesforce,
    SalesforceMalformedRequest,
    SalesforceResourceNotFound,
)

# importing functions
from utils import *
from logger_config import logger


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
        # Extract Salesforce details from Secrets Manager
        secret_name = os.environ["secret_name"]
        secret_region_name = os.environ["secret_region_name"]

        salesforce_secret = get_secret(secret_name, secret_region_name)

        # Check if Salesforce secret is None
        if salesforce_secret is None:
            logger.info(f"salesforce_secret is {salesforce_secret}")
            error_message = "Error in getting Salesforce secrets from Secret Manager"
            logger.info(error_message)
            return {"statusCode": 500, "body": json.dumps({"message": error_message})}

        # Access Salesforce secret values
        username = salesforce_secret.get("user_name")
        password = salesforce_secret.get("password")
        security_token = salesforce_secret.get("security_token")
        domain = salesforce_secret.get("domain")

        # Extract Bedrock model ID and DynamoDB tables
        model_id = os.environ["model_id"]
        chat_history_table = os.environ["chat_history_table"]
        leads_table = os.environ["leads_table_name"]

        # Extract region names
        bedrock_region_name = os.environ["bedrock_region_name"]
        dynamodb_region_name = os.environ["dynamodb_region_name"]

        # Extract guardrail ID and version
        guardrail_id = os.environ["guardrail_id"]
        guardrail_version = os.environ["guardrail_version"]

        # Getting Bedrock client
        bedrock_runtime = get_bedrock_client(bedrock_region_name)
        if bedrock_runtime is None:
            error_message = "Error in creating bedrock runtime"
            logger.info(error_message)
            return {"statusCode": 500, "body": json.dumps({"message": error_message})}

        # Get DynamoDB client
        dynamodb_client = get_dynamodb_client(dynamodb_region_name)
        if dynamodb_client is None:
            error_message = "Error in creating dynamodb client"
            logger.info(error_message)
            return {"statusCode": 500, "body": json.dumps({"message": error_message})}

        # session ids with no lead ids in leads table
        extracted_session_ids = session_ids_with_no_lead_id(
            dynamodb_client, leads_table
        )
        logger.info(f"extracted_session_ids is {extracted_session_ids}")

        # Get Salesforce object
        salesforce_object = get_salesforce_object(
            username, password, security_token, domain
        )
        if salesforce_object is None:
            error_message = "unable to get salesforce object from given credentials"
            logger.info(error_message)
            return {
                "statusCode": 500,
                "body": json.dumps({"message": error_message}),
            }

        # iterate through each session ids
        for session_id in extracted_session_ids:
            logger.info(f"session_id is {session_id}")

            # get chat history
            chat_history = get_session_history(
                session_id, chat_history_table, dynamodb_client
            )

            # get user inputs from chat history
            user_inputs = [
                entry["content"][0]["text"]
                for entry in chat_history
                if entry["role"] == "user"
            ]
            logger.info(f"user_inputs is {user_inputs}")

            try:
                # Get previous lead creation attempts
                previous_lead_creation_attempts = retrieve_previous_user_info(
                    dynamodb_client, leads_table, session_id
                )

                # Load user details extraction prompt
                try:
                    with open("prompts/extraction_instructions.txt") as f:
                        user_details_extraction_prompt = f.read()
                except Exception as e:
                    error_message = f"Error reading extraction instructions: {e}"
                    logger.info(error_message)
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"message": error_message}),
                    }

                # Trying lead creation for only 4 times.
                if previous_lead_creation_attempts < 4:
                    # extracting user details
                    user_details = extract_user_details(
                        user_inputs,
                        user_details_extraction_prompt,
                        model_id,
                        bedrock_runtime,
                    )

                    if user_details is None:
                        error_message = f"Unable to extract user details for session ID {session_id}"
                        logger.info(error_message)
                        continue  # Skip to the next session ID if user details extraction fails

                    # parsing user details
                    user_details_dict = parse_user_details(user_details)
                    user_details_dict = validate_user_info(user_details_dict)
                    logger.info(f"user_details_dict is {user_details_dict}")

                    # crosschecking if email, phone number and first name is present or not.
                    if (
                        (
                            user_details_dict["FirstName"]
                            or user_details_dict["LastName"]
                        )
                        and (user_details_dict["Email"])
                        and (user_details_dict["Phone"])
                    ):
                        if not user_details_dict["LastName"]:
                            user_details_dict["LastName"] = user_details_dict[
                                "FirstName"
                            ]
                            user_details_dict["FirstName"] = None

                        try:
                            lead_creation_attempts = 0
                            lead_creation_message = "None"
                            # loading summary prompt
                            with open("prompts/summary_instructions.txt") as f:
                                summary_extraction_prompt = f.read()

                            if len(chat_history) % 2 != 0:
                                chat_history = chat_history[:-1]
                                logger.info(f"odd number of chat history elemnts")

                            conversation_history_list = format_conversation_history(
                                chat_history
                            )
                            summary = generate_conversation_summary(
                                conversation_history_list,
                                bedrock_runtime,
                                model_id,
                                summary_extraction_prompt,
                                session_id
                            )

                            (
                                lead_id,
                                lead_creation_message,
                                lead_creation_attempts,
                            ) = lead_creation(
                                user_details_dict,
                                salesforce_object,
                                summary,
                                dynamodb_client,
                                leads_table,
                            )
                            lead_creation_attempts = (
                                lead_creation_attempts + previous_lead_creation_attempts
                            )
                        except Exception as e:
                            logger.info(
                                f"Exception {e} occured while creating the lead"
                            )
                            lead_creation_message = (
                                f"Exception {e} occured while creating the lead"
                            )
                            lead_id = None
                            try:
                                lead_creation_attempts = (
                                    previous_lead_creation_attempts + 1
                                )
                            except Exception as e:
                                lead_creation_attempts = 1

                        if lead_id is None:
                            lead_id = "None"
                            lead_creation_status = False
                        else:
                            lead_creation_status = True
                        logger.info(
                            f"lead creation status for lead id {lead_id} is {lead_creation_message}"
                        )
                        user_details_dict.pop("Description", None)
                        update_leads_table(
                            dynamodb_client,
                            leads_table,
                            session_id,
                            user_details_dict,
                            summary,
                            user_inputs,
                            lead_creation_attempts,
                            lead_id,
                            lead_creation_status,
                            lead_creation_message,
                        )
                    else:
                        error_message = f"mandatory user deatils are not present to create lead for session id is {session_id}"
                        logger.info(error_message)
            except Exception as e:
                logger.info(f"Error processing session ID {session_id}: {e}")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "successfully created lead ids"}),
        }
    except Exception as e:
        error_message = f"Error during creating lead: {e}"
        return {"statusCode": 500, "body": json.dumps({"message": error_message})}
