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

        # Get recent session IDs for which lead is already created
        hours_filter = 48  # in hours
        recent_session_ids = extract_recent_session_ids(
            dynamodb_client, leads_table, hours_filter
        )
        logger.info(f"recent_session_ids is {recent_session_ids}")
        if recent_session_ids is None:
            error_message = f"Error extracting recent session IDs"
            logger.info(error_message)
            return {"statusCode": 500, "body": json.dumps({"message": error_message})}

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

        # Process recent session IDs
        if len(recent_session_ids) > 0:
            for session_id in recent_session_ids:
                logger.info(f"session_id is {session_id}")
                try:
                    # Check if chat history updated in last number of  hours
                    hours_filter = 48 # In hours
                    recent_chat_history_flag = is_recent_chat_history(
                        dynamodb_client, chat_history_table, session_id, hours_filter
                    )
                    if recent_chat_history_flag:
                        try:
                            chat_history = get_session_history(
                                session_id, chat_history_table, dynamodb_client
                            )
                            user_inputs = [
                                entry["content"][0]["text"]
                                for entry in chat_history
                                if entry["role"] == "user"
                            ]
                            logger.info(f"new user inputs is {user_inputs}")

                            # Get previous user details
                            (
                                previous_user_details,
                                lead_id,
                                previous_user_inputs,
                                lead_update_attempts,
                            ) = retrieve_previous_user_info(
                                dynamodb_client, leads_table, session_id
                            )
                            logger.info(
                                f"previous_user_details is {previous_user_details}"
                            )
                            logger.info(f"lead_id is {lead_id}")
                            logger.info(
                                f"previous_user_inputs is {previous_user_inputs}"
                            )
                            logger.info(
                                f"lead_update_attempts is {lead_update_attempts}"
                            )

                            updated_list = find_updated_list_with_values(
                                previous_user_inputs, user_inputs
                            )
                            logger.info(f"updated_list is {updated_list}")

                            if (len(updated_list) > 0) and (lead_update_attempts < 4):
                                # Load user details extraction prompt
                                try:
                                    with open("prompts/extraction_instructions.txt") as f:
                                        user_details_extraction_prompt = f.read()
                                except Exception as e:
                                    error_message = f"Error reading extraction instructions: {e}"
                                    logger.info(error_message)
                                    return {"statusCode": 500, "body": json.dumps({"message": error_message})}
                                            
                                # Extracting user details and parsing them
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

                                user_details_dict = parse_user_details(user_details)
                                user_details_dict = validate_user_info(
                                    user_details_dict
                                )
                                logger.info(f"user_details_dict is {user_details_dict}")

                                # Crosschecking if email, phone number, and first name are present or not
                                if (
                                    (
                                        user_details_dict.get("FirstName")
                                        or user_details_dict.get("LastName")
                                    )
                                    and user_details_dict.get("Email")
                                    and user_details_dict.get("Phone")
                                ):
                                    if not user_details_dict["LastName"]:
                                        user_details_dict[
                                            "LastName"
                                        ] = user_details_dict["FirstName"]
                                        user_details_dict["FirstName"] = None

                                    # Get updated values of the dict
                                    updated_dict = find_updated_keys_with_values(
                                        previous_user_details, user_details_dict
                                    )
                                    logger.info(f"updated_dict is {updated_dict}")

                                    if len(updated_dict) > 0:
                                        try:
                                            with open(
                                                "prompts/summary_instructions.txt"
                                            ) as f:
                                                summary_extraction_prompt = f.read()

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
                                            logger.info(
                                                f"updated_dict is {updated_dict}"
                                            )
                                            logger.info(f"started updating lead id")
                                            update_lead_flag = update_lead_id(
                                                salesforce_object,
                                                lead_id,
                                                user_details_dict,
                                                summary,
                                                session_id,
                                                dynamodb_client, 
                                                leads_table,
                                            )
                                            logger.info(
                                                f"update_lead_flag is {update_lead_flag}"
                                            )
                                            lead_update_attempts = (
                                                lead_update_attempts + 1
                                            )
                                            if update_lead_flag:
                                                user_details_dict.pop("Description", None)
                                                update_leads_table_flag = update_leads_table(
                                                    dynamodb_client,
                                                    leads_table,
                                                    session_id,
                                                    user_details_dict,
                                                    summary,
                                                    user_inputs,
                                                    lead_update_attempts,
                                                )
                                            else:
                                                logger.info(
                                                    f"update_lead_flag is {update_lead_flag} and not updating the leads table."
                                                )
                                        except Exception as e:
                                            logger.info(
                                                f"Error in updating the lead ID: {e}"
                                            )
                        except Exception as e:
                            logger.info(
                                f"Error processing session ID {session_id}: {e}"
                            )
                except Exception as e:
                    logger.info(
                        f"Error in getting recent chat history for session id {session_id}: {e}"
                    )
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "successfully updated lead ids"}),
        }
    except Exception as e:
        error_message = f"Error during lead update process: {e}"
        return {"statusCode": 500, "body": json.dumps({"message": error_message})}
