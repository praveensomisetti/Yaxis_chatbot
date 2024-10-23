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
        # Extract user query and session id from event dict
        user_query = event["user_query"]
        session_id = event["session_id"]

        logger.info(f"session id is {session_id}")
        logger.info(f"user query before cleaning is {user_query}")

        # clean user query
        user_query = clean_user_query(user_query)
        logger.info(f"user query after cleaning is {user_query}")

        # extract salesforce details from secrets manager
        secret_name = os.environ["secret_name"]
        secret_region_name = os.environ["secret_region_name"]

        salesforce_secret = get_secret(secret_name, secret_region_name)

        final_output = {}
        final_output["lead_type"] = "Not Qualified"
        final_output[
            "lead_creation_message"
        ] = "User conversation not Qualified for creating salesforce lead"

        # checking if salesforce secret is none or not
        if salesforce_secret is None:
            logger.info(f"salesforce_secret is {salesforce_secret}")
            error_message = "Error in getting salesforce secrets from secret manager"
            logger.info(error_message)
            final_output["lead_creation_message"] = error_message
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

        # loading user details extraction prompt
        try:
            with open("prompts/extraction_instructions.txt") as f:
                user_details_extraction_prompt = f.read()
        except Exception as e:
            error_message = f"Error reading extraction instructions: {e}"
            logger.info(error_message)
            return {"statusCode": 500, "body": json.dumps({"message": error_message})}

        # getting bedrock client
        bedrock_runtime = get_bedrock_client(bedrock_region_name)

        if bedrock_runtime is None:
            error_message = "Error in creating bedrock runtime"
            logger.info(error_message)
            final_output["lead_creation_message"] = error_message
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        # get dynamodb client
        dynamodb_client = get_dynamodb_client(dynamodb_region_name)

        if dynamodb_client is None:
            error_message = "Error in creating dynamodb client"
            logger.info(error_message)
            final_output["lead_creation_message"] = error_message
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        # get chat history
        chat_history = get_session_history(
            session_id, chat_history_table, dynamodb_client
        )

        if chat_history is None:
            error_message = "Error in getting chat history"
            logger.info(error_message)
            final_output["lead_creation_message"] = error_message
            logger.info(f"lambda response is {final_output}")
            return {"statusCode": 500, "body": json.dumps(final_output)}

        logger.info(f"length of chat_history is {len(chat_history)}")

        if (
            user_query is not None
            and isinstance(user_query, str)
            and len(user_query.strip()) > 0
        ):
            # create conversation message.
            conversation = [{"role": "user", "content": [{"text": user_query}]}]
            chat_history = chat_history + conversation

        # get user inputs from chat history
        user_inputs = [
            entry["content"][0]["text"]
            for entry in chat_history
            if entry["role"] == "user"
        ]
        logger.info(f"user_inputs is {user_inputs}")
        logger.info(f"user_inputs length is {len(user_inputs)}")

        # Lead creation process
        if len(user_inputs) > 5:
            final_output["lead_type"] = "Qualified"
            # checking whether session id is already there in the table or not
            session_id_present = check_session_id_and_status(
                session_id, leads_table_name, dynamodb_client
            )
            logger.info(f"Session id available in leads table is {session_id_present}")
            if not session_id_present:
                try:
                    # extracting user details and parsing them
                    user_details = extract_user_details(
                        user_inputs,
                        user_details_extraction_prompt,
                        model_id,
                        bedrock_runtime,
                    )

                    if user_details is None:
                        final_output[
                            "lead_creation_message"
                        ] = "unable to extract user details from user inputs"
                        logger.info(f"lambda response is {final_output}")
                        return {
                            "statusCode": 500,
                            "body": json.dumps(final_output),
                        }

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
                            lead_creation_message = "None"
                            # get salesforce object, conversation summary and creating lead in system
                            salesforce_object = get_salesforce_object(
                                username, password, security_token, domain
                            )

                            if salesforce_object is None:
                                final_output[
                                    "lead_creation_message"
                                ] = "unable to get salesforce object from given credentials"
                                logger.info(f"lambda response is {final_output}")
                                return {
                                    "statusCode": 500,
                                    "body": json.dumps(final_output),
                                }

                            # loading summary prompt
                            with open("prompts/summary_instructions.txt") as f:
                                summary_extraction_prompt = f.read()

                            if len(chat_history) % 2 != 0:
                                chat_history = chat_history[:-1]
                                logger.info(f"odd number of chat history elemnts")

                            # Generate conversation summary
                            conversation_history_list = format_conversation_history(
                                chat_history
                            )
                            summary = generate_conversation_summary(
                                conversation_history_list,
                                bedrock_runtime,
                                model_id,
                                summary_extraction_prompt,
                                session_id,
                            )

                            # Lead creation in Salesforce
                            (
                                lead_id,
                                lead_creation_message,
                                lead_creation_attempts,
                            ) = lead_creation(
                                user_details_dict,
                                salesforce_object,
                                summary,
                                dynamodb_client,
                                leads_table_name,
                            )
                        except Exception as e:
                            logger.info(
                                f"Exception {e} occured while creating the lead"
                            )
                            lead_creation_message = (
                                f"Exception {e} occured while creating the lead"
                            )
                            lead_id = None
                            lead_creation_attempts = 1

                        if lead_id is None:
                            lead_id = "None"
                            lead_creation_status = False
                        else:
                            lead_creation_status = True
                        logger.info(
                            f"lead creation status for lead id {lead_id} is {lead_creation_message}"
                        )
                        final_output["lead_creation_message"] = lead_creation_message
                        user_details_dict.pop("Description", None)
                        lead_update_attempts = 0
                        insert_lead_to_dynamodb(
                            session_id,
                            lead_id,
                            lead_creation_status,
                            lead_creation_message,
                            user_details_dict,
                            summary,
                            user_inputs,
                            lead_creation_attempts,
                            lead_update_attempts,
                            leads_table_name,
                            dynamodb_client,
                        )
                    else:
                        lead_creation_message = (
                            "mandatory user deatils are not present to create lead"
                        )
                        final_output["lead_creation_message"] = lead_creation_message
                        lead_update_attempts = 0
                        lead_id = "None"
                        lead_creation_status = False
                        summary = "None"
                        user_details_dict.pop("Description", None)
                        lead_creation_attempts = 1
                        insert_lead_to_dynamodb(
                            session_id,
                            lead_id,
                            lead_creation_status,
                            lead_creation_message,
                            user_details_dict,
                            summary,
                            user_inputs,
                            lead_creation_attempts,
                            lead_update_attempts,
                            leads_table_name,
                            dynamodb_client,
                        )
                except Exception as e:
                    logger.info(f"Exception {e} occured while extracting user details")
                    final_output[
                        "lead_creation_message"
                    ] = f"Exception {e} occured while extracting user details"
            else:
                final_output[
                    "lead_creation_message"
                ] = f"session id {session_id} is already present in leads table"
        logger.info(f"lambda response is {final_output}")
        return {
            "statusCode": 200,
            "body": json.dumps(final_output),
        }

    except Exception as e:
        # Handle and log any exceptions
        error_message = (
            f"Error during lead creation process, session_id: {session_id}, error: {e}"
        )
        logger.error(error_message)
        final_output = {}
        final_output["lead_type"] = "Error occured while running lead creation process"
        final_output["lead_creation_message"] = error_message
        logger.info(f"lambda response is {final_output}")
        return {"statusCode": 500, "body": json.dumps(final_output)}
