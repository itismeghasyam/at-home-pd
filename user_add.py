import bridgeclient as bc
import synapseclient as sc
import argparse

INPUT_TABLE = "syn16784393"
OUTPUT_TABLE = "syn16786935"

def read_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridgeUsername")
    parser.add_argument("--bridgePassword")
    parser.add_argument("--synapseUsername")
    parser.add_argument("--synapsePassword")
    args = parser.parse_args()
    return args


def get_new_users(syn, input_table = INPUT_TABLE, output_table = OUTPUT_TABLE):
    input_table_df = syn.tableQuery(
            "select * from {}".format(input_table)).asDataFrame()
    input_table_df = input_table_df.set_index("phone_number", drop=False)
    output_table_df = syn.tableQuery(
            "select phone_number from {}".format(output_table)).asDataFrame()
    new_numbers = set(input_table_df.phone_number.values).difference(
            output_table_df.phone_number.values)
    return input_table_df.loc[list(new_numbers)]


def get_bridge_client(bridge_username, bridge_password, study="sage-mpower-2"):
    bridge = bc.bridgeConnector(
            email = bridge_username, password = bridge_password, study = study)
    return bridge


def get_participant_info(bridge, phone_number):
    participant_info = bridge.restPOST(
            "/v3/participants/search",
            {"phoneFilter": phone_number})
    return participant_info


def process_request(bridge, participant_info, phone_number, external_id):
    if participant_info['total'] == 0:
        # create account
        try:
            bridge.restPOST("/v3/externalIds", [external_id])
            bridge.restPOST(
                    "/v3/participants",
                    {"externalId": external_id,
                     "phone": {"number": phone_number,
                               "regionCode": "US"},
                     "dataGroups": "clinical_consent"}) # assume US?
            return "Success: User account created"
        except Exception as e:
            return ("Error: Could not create user account. "
                    "Console output: {0}".format(e))
    elif 'externalId' not in participant_info['items'][0]:
        try:
            # add external_id and then assign to existing account
            user_id = participant_info['items'][0]['id']
            bridge.restPOST("/v3/externalIds", [external_id])
            bridge.restPOST(
                    "/v3/participants/{}".format(user_id),
                    {"externalId": external_id})
            return ("Success: Preexisting user account found. "
                    "New External ID assigned.")
        except Exception as e:
            return ("Error: Preexising user account found. "
                    "Could not assign new external ID. "
                    "Console output: {0}".format(e))
    elif participant_info['items'][0]['externalId'] != external_id:
        # phone and external ID have already been assigned
        return ("Error: Preexisting account found with guid {}. "
                "Please contact larsson.omberg@sagebase.org "
                "if you would like to assign a new guid.".format(
                    participant_info['items'][0]['externalId']))
    elif participant_info['items'][0]['externalId'] == external_id:
        # account exists and is correct, do nothing
        return ("Success: Preexisting account found with matching phone number "
                "and guid.")


def create_table_row(status, phone_number, guid,
                     visit_date, output_table = OUTPUT_TABLE):
    table_values = [int(phone_number), guid, visit_date, status]
    return table_values


def main():
    args = read_args()
    syn = sc.login(args.synapseUsername, args.synapsePassword)
    new_users = get_new_users(syn)
    duplicated_numbers = new_users.phone_number.duplicated(keep = False)
    if any(duplicated_numbers):
        duplicates = new_users.loc[duplicated_numbers]
        if len(duplicates.guid) == len(duplicates.guid.unique()):
            table_row = create_table_row("Error: It looks like you accidentally "
                                         "entered an incorrect guid and tried to "
                                         "submit a corrected one immediately "
                                         "afterwards. Please delete the duplicate "
                                         "phone number from the Users table "
                                         "(syn16784393) and this table (syn16786935) "
                                         "and resubmit.", duplicates.phone_number.iloc[0],
                                         "", duplicates.visit_date.iloc[0])
        syn.store(sc.Table(OUTPUT_TABLE, [table_row]))
        return
    to_append_to_table = []
    for i, user in new_users.iterrows():
        try:
            if not (len(user.phone_number) == 10 and user.phone_number.isdigit()):
                table_row = create_table_row("Error: The phone number is improperly "
                                             "formatted. Please enter a valid, 10-digit "
                                             "number",
                                             user.phone_number, user.guid, user.visit_date)
            else:
                bridge = get_bridge_client(args.bridgeUsername, args.bridgePassword)
                participant_info = get_participant_info(bridge, user.phone_number)
                status = process_request(bridge, participant_info,
                                         user.phone_number, user.guid)
                table_row = create_table_row(status, user.phone_number,
                                             user.guid, user.visit_date)
        except Exception as e:
            table_row = create_table_row("Error: One of the fields is improperly "
                                         "formatted. Console output: {0}".format(e),
                                         -1, user.guid, user.visit_date)
        to_append_to_table.append(table_row)
    if len(to_append_to_table):
        syn.store(sc.Table(OUTPUT_TABLE, to_append_to_table))


if __name__ == "__main__":
    main()
