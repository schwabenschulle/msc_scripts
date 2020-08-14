#!/usr/bin/env python

import requests
import  json
import lib.vars as var
import sys, time
import urllib3
import argparse
import os, logging
import sdk.mso as msc
try:
    from sdk.credentials import MSO_IP, MSO_ADMIN, MSO_PASSWORD
except ImportError:
    sys.exit("Error: please verify credentials file format.")
import lib.mso as mso

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="MSITE BD & EPG import")
    parser.add_argument('-sch', '--schema', required=True)
    parser.add_argument('-s_tmp', '--source_template', required=True)
    parser.add_argument('-t_tmp', '--target_template', required=True)
    parser.add_argument('-bd', '--bridge_domain', required=True)
    parser.add_argument('-epg', '--endpoint_grpup', required=True)
    parser.add_argument('-anp', '--anp', required=True)
    parser.add_argument('-d', '--deploy', default=False, action="store_true")
    parser.add_argument('-vvv', '--verbose', default=False, action="store_true")
    args = parser.parse_args()

    sourceTemplateName = args.source_template
    targetTemplateName = args.target_template
    bdNameToMigrate = args.bridge_domain
    egpNameToMigrate = args.endpoint_grpup
    anpToMigrate = args.anp
    schemaName = args.schema


    # logger
    logging.basicConfig(level=logging.INFO)

    logfh = logging.FileHandler(os.path.join('log', 'migrate_epg_bd.log'))
    logger = logging.getLogger('migrate_epg_bd')
    logger.addHandler(logfh)
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logfh.setFormatter(formatter)
    logger.setLevel(logging.INFO)

    ''' If verbose change logging level to debug'''
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    '''Login in MSO'''
    logger.info("Login to MSO")
    rc = msc.RestClient(MSO_IP, MSO_ADMIN, MSO_PASSWORD)

    ''' get schema id'''
    logger.info("Getting Schema ID")
    response = rc.get('/schemas')
    schema_item, response  = mso.filter_class(response.json(), {'fclass' : 'schemas', 'attr' : 'displayName', 'value' : schemaName})

    if not schema_item:
        logger.error(f"Schema: {schemaName} not found")
        sys.exit()

    ''' check whether templates exist and map template name and display name'''

    template_dict = mso.check_template_name(schema_item,sourceTemplateName)
    mso.check_template_name(schema_item, targetTemplateName)
    migration_obj = mso.migration(**{"targetSchemaId" : schema_item['id'], "targetTemplateName" : targetTemplateName})
    if bdNameToMigrate:
        migration_obj.bds.append({ "name": bdNameToMigrate})

    if egpNameToMigrate:
        migration_obj.anps = [{ "name": anpToMigrate, "epgs" : [{"name" : egpNameToMigrate}]}]

    logger.info("Sending PUT Call to MSO")
    migrate_payload = migration_obj. __dict__
    logger.debug(json.dumps(migrate_payload, sort_keys=True, indent=2, separators=(',', ':')))

    response = rc.post(f"/migrate/schema/{schema_item['id']}/template/{sourceTemplateName}", **{"json_body": migrate_payload})

    if response.status_code != 200:
        logger.error(response.content)
    else:
        logger.info(f"Migration {egpNameToMigrate} from {sourceTemplateName} to {targetTemplateName} successfull")
        logger.debug(json.dumps(response.text, sort_keys=True, indent=2, separators=(',', ':')))

    '''Check whether target template is streched or site local Result True or False'''
    target_stretched_template, siteIdtarget = mso.template_streched_check(schema_item, template_dict[targetTemplateName])
    source_stretched_template, siteIdsource = mso.template_streched_check(schema_item, template_dict[sourceTemplateName])

    logger.info(f"Lookup for Object {bdNameToMigrate} which is supposed to be stretched")
    response = rc.get('/schemas')
    schema_item, response = mso.filter_class(response.json(),{'fclass': 'schemas', 'attr': 'displayName', 'value': schemaName})

    template_item, response = mso.filter_class(schema_item, {'fclass' : 'templates', 'attr' : 'name', 'value' : targetTemplateName })
    bd_item, response = mso.filter_class(template_item, {'fclass' : 'bds', 'attr' : 'name', 'value' : bdNameToMigrate})
    if not bd_item:
        logger.error(f"BD: {bdNameToMigrate} not found in Template: {targetTemplateName}")
        sys.exit(0)

    ''' check whether site reference item exist and give True/False and the item back'''
    site_ref_state,site_ref_item = mso.template_site_ref_check(targetTemplateName, schema_item, "bds", bdNameToMigrate, "bdRef")
    template_item, response = mso.filter_class(schema_item,{'fclass': 'templates', 'attr': 'name', 'value': targetTemplateName})
    bd_item, response = mso.filter_class(template_item, {'fclass': 'bds', 'attr': 'name', 'value': bdNameToMigrate})

    if not target_stretched_template and source_stretched_template:
        l3out_list = []
        ''' if a site ref exist search for subnet add subnet to a list and collect l3out infos for all sites'''
        if site_ref_state:
            for site_ref in site_ref_item:
                if site_ref['subnets']:
                    for subnet in site_ref['subnets']:
                        logger.info(f"Migrate Subnets {subnet} for site-local to template {targetTemplateName}")
                        bd_item['subnets'].append(subnet)

#                if site_ref['l3Outs']:
#                    logger.info(f"Collect L3OUT {site_ref['l3Outs']} from all sites")
#                    for l3out in site_ref['l3Outs']:
#                        l3out_list.append(l3out)

        ''' get schema and update bd attribute, remove subnet in site-level and put schema'''
        response = rc.get(f"/schemas/{schema_item['id']}")
        schema_definition = response.json()

        '''Add subent in template and change l2Stretch to False must be done in one put'''
        for site in schema_definition['sites']:
            if site['templateName'] == targetTemplateName:
                for bd in site['bds']:
                    if bdNameToMigrate in bd['bdRef'] and not bd['subnets']:
                        bd['subnets'] = bd_item['subnets']
                        subnet_ref_list = bd['subnets']
                        logger.info("Add Subnets to Site-Level")

        for template in schema_definition['templates']:
            if template['displayName'] == targetTemplateName:
                for bd in template['bds']:
                    if bd['name'] == bdNameToMigrate:
                        bd['l2Stretch'] = False
                        bd['optimizeWanBandwidth'] = False
                        bd['intersiteBumTrafficAllow'] = False
                        bd['subnets'] = []

        response = rc.put(f"/schemas/{schema_item['id']}", **{"json_body": schema_definition})
        if response.status_code != 200:
            logger.error(response.content)
        else:
            logger.info(f"Schema Update successfull")
        logger.debug(json.dumps(response.text, sort_keys=True, indent=2, separators=(',', ':')))
        if response.status_code != 200:
            logger.error(response.content)
        else:
            logger.info(f"Update Template Subnet successfull")
            logger.debug(response.content)


    ''' if target id stretched template and source non stretched template'''
    if target_stretched_template and not source_stretched_template:
        l3out_list = []
        ''' if a site ref exist search for subnet add subnet to a list and collect l3out infos for all sites'''
        if site_ref_state:
            for site_ref in site_ref_item:
                if site_ref['subnets']:
                    for subnet in site_ref['subnets']:
                        logger.info(f"Migrate Subnets {subnet} for site-local to template {targetTemplateName}")
                        bd_item['subnets'].append(subnet)
                if site_ref['l3Outs']:
                    logger.info(f"Collect L3OUT {site_ref['l3Outs']} from all sites")
                    for l3out in site_ref['l3Outs']:
                        l3out_list.append(l3out)

            ''' set a common l3out list to all site for target Template'''
            if l3out_list:
                for site_ref in site_ref_item:
                    site_ref['l3Outs'] = l3out_list

        ''' get schema and update bd attribute, remove subnet in site-level and put schema'''
        response = rc.get(f"/schemas/{schema_item['id']}")
        schema_definition = response.json()

        '''Delete subent in site and change l2Stretch to True must be done in one put'''
        for site in schema_definition['sites']:
            if site['templateName'] == targetTemplateName:
                for bd in site['bds']:
                    if bdNameToMigrate in bd['bdRef'] and bd['subnets']:
                        bd['subnets'] = []
                        logger.info("Removing Subnets from Site-Level")

        for template in schema_definition['templates']:
            if template['displayName'] == targetTemplateName:
                for bd in template['bds']:
                    if bd['name'] == bdNameToMigrate:
                        bd['subnets'] = bd_item['subnets']
                        bd['l2Stretch'] = True
                        bd['intersiteBumTrafficAllow'] = True
                        bd['optimizeWanBandwidth'] = True
                        if bd_item['subnets']:
                            bd['intersiteBumTrafficAllow'] = False
                            bd['optimizeWanBandwidth'] = False


        response = rc.put(f"/schemas/{schema_item['id']}", **{"json_body": schema_definition})
        if response.status_code != 200:
            logger.error(response.content)
        else:
            logger.info(f"Schema Update successfull")
        logger.debug(json.dumps(response.text, sort_keys=True, indent=2, separators=(',', ':')))

        ''' subnet site level configuration l3 out sync Loop through all site for a template add BD-REF ITEM if needed and patch l3out'''
        for siteId_item in siteIdtarget:
            bd_obj = mso.bd(**{"bdName": bdNameToMigrate})
            bd_obj.path = (f"/sites/{siteId_item}-{targetTemplateName}/bds/-")
            bd_obj.value['bdRef'] = {"schemaId": schema_item['id'], "templateName": targetTemplateName,"bdName": bdNameToMigrate}
            bd_obj.value['3Outs'] =  []
            body_chg_bd = bd_obj.__dict__
            response = rc.patch(f"/schemas/{schema_item['id']}", **{"json_body": [body_chg_bd]})

            bd_obj = mso.bd(**{"bdName": bdNameToMigrate})
            bd_obj.update(f"/sites/{siteId_item}-{targetTemplateName}/bds/{bdNameToMigrate}/l3Outs")
            bd_obj.value = l3out_list
            body_chg_bd = bd_obj.__dict__
            response = rc.patch(f"/schemas/{schema_item['id']}", **{"json_body":[body_chg_bd] })

            if response.status_code != 200:
               logger.error(response.content)
            else:
               logger.info(f"Update Site-ID  {siteId_item} L3OUT {l3out_list} successfull")
               logger.debug(response.content)

    if args.deploy:
        time.sleep(1)
        logger.info(f"Deploying Target Template {targetTemplateName}")
        response = rc.get(f"/execute/schema/{schema_item['id']}/template/{targetTemplateName}")
        logger.info(response.content)

        logger.info(f"Deploying Source Template {sourceTemplateName}")
        response = rc.get(f"/execute/schema/{schema_item['id']}/template/{sourceTemplateName}")
        logger.info(response.content)

