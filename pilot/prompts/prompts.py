# prompts/prompts.py
from utils.style import color_white_bold, THEME_STYLES, Theme
from const import common
from const.llm import MAX_QUESTIONS, END_RESPONSE
from utils.llm_connection import create_gpt_chat_completion
from utils.utils import get_sys_message, get_prompt
from utils.questionary import styled_select, styled_text
from logger.logger import logger


def ask_for_app_type():
    return 'App'
    answer = styled_select(
        "What type of app do you want to build?",
        choices=common.APP_TYPES
    )

    if answer is None:
        print("Exiting application.")
        exit(0)

    while 'unavailable' in answer:
        print("Sorry, that option is not available.")
        answer = styled_select(
            "What type of app do you want to build?",
            choices=common.APP_TYPES
        )
        if answer is None:
            print("Exiting application.")
            exit(0)

    print("You chose: " + answer)
    logger.info(f"You chose: {answer}")
    return answer


def ask_for_main_app_definition(project):
    description = styled_text(
        project,
        "Describe your app in as much detail as possible."
    )

    if description is None:
        print("No input provided!")
        return

    logger.info(f"Initial App description done: {description}")

    return description


def ask_user(project, question: str, require_some_input=True, hint: str = None):
    while True:
        if hint is not None:
            print(color_white_bold(question), type='hint')
            style = THEME_STYLES[Theme.YELLOW]
            answer = styled_text(project, hint, style=style)
        else:
            answer = styled_text(project, question)

        logger.info('Q: %s', question)
        logger.info('A: %s', answer)

        if answer is None:
            print("Exiting application.")
            exit(0)

        if answer.strip() == '' and require_some_input:
            print("No input provided! Please try again.")
            continue
        else:
            return answer


def get_additional_info_from_openai(project, messages):
    """
    Runs the conversation between Product Owner and LLM.
    Provides the user's initial description, LLM asks the user clarifying questions and user responds.
    Limited by `MAX_QUESTIONS`, exits when LLM responds "EVERYTHING_CLEAR".

    :param project: Project
    :param messages: [
        { "role": "system", "content": "You are a Product Owner..." },
        { "role": "user", "content": "I want you to create the app {name} that can be described: ```{description}```..." }
      ]
    :return: The updated `messages` list with the entire conversation between user and LLM.
    """
    is_complete = False
    while not is_complete:
        # Obtain clarifications using the OpenAI API
        # { 'text': new_code }
        response = create_gpt_chat_completion(messages, 'additional_info', project)

        if response is not None:
            if response['text'] and response['text'].strip() == END_RESPONSE:
                # print(response['text'] + '\n')
                break

            # Ask the question to the user
            answer = ask_user(project, response['text'])

            # Add the answer to the messages
            messages.append({'role': 'assistant', 'content': response['text']})
            messages.append({'role': 'user', 'content': answer})
        else:
            is_complete = True

    logger.info('Getting additional info from openai done')

    return [msg for msg in messages if msg['role'] != 'system']


# TODO refactor this to comply with AgentConvo class
def generate_messages_from_description(description, app_type, name):
    """
    Called by ProductOwner.get_description().
    :param description: "I want to build a cool app that will make me rich"
    :param app_type: 'Web App', 'Script', 'Mobile App', 'Chrome Extension' etc
    :param name: Project name
    :return: [
        { "role": "system", "content": "You are a Product Owner..." },
        { "role": "user", "content": "I want you to create the app {name} that can be described: ```{description}```..." }
      ]
    """
    # "I want you to create the app {name} that can be described: ```{description}```
    prompt = get_prompt('high_level_questions/specs.prompt', {
        'name': name,
        'prompt': description,
        'app_type': app_type,
    })

    # Get additional answers
    # Break down stories
    # Break down user tasks
    # Start with Get additional answers
    # {prompts/components/no_microservices}
    # {prompts/components/single_question}
    specs_instructions = get_prompt('high_level_questions/specs_instruction.prompt', {
            'name': name,
            'app_type': app_type,
            # TODO: MAX_QUESTIONS should be configurable by ENV or CLI arg
            'MAX_QUESTIONS': MAX_QUESTIONS
        })

    return [
        get_sys_message('product_owner'),
        {'role': 'user', 'content': prompt},
        {'role': 'system', 'content': specs_instructions},
    ]


def generate_messages_from_custom_conversation(role, messages, start_role='user'):
    """
    :param role: 'product_owner', 'architect', 'dev_ops', 'tech_lead', 'full_stack_developer', 'code_monkey'
    :param messages: [
        "I will show you some of your message to which I want you to make some updates. Please just modify your last message per my instructions.",
        {LLM's previous message},
        {user's request for change}
    ]
    :param start_role: 'user'
    :return: [
      { "role": "system", "content": "You are a ..., You do ..." },
      { "role": start_role, "content": messages[i + even] },
      { "role": "assistant" (or "user" for other start_role), "content": messages[i + odd] },
      ... ]
    """
    # messages is list of strings
    system_message = get_sys_message(role)
    result = [system_message]
    logger.info(f'\n>>>>>>>>>> {role} Prompt >>>>>>>>>>\n%s\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>', system_message['content'])

    for i, message in enumerate(messages):
        if i % 2 == 0:
            result.append({"role": start_role, "content": message})
            logger.info(f'\n>>>>>>>>>> {start_role} Prompt >>>>>>>>>>\n%s\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>', message)
        else:
            result.append({"role": "assistant" if start_role == "user" else "user", "content": message})
            logger.info('\n>>>>>>>>>> Assistant Prompt >>>>>>>>>>\n%s\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>', message)

    return result
