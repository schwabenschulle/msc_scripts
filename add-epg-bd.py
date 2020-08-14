import  json
import lib.vars as var
import lib.mso as mso
import sys,re
import urllib3
import argparse
import os, logging
import sdk.mso as msc
try:
    from sdk.credentials import MSO_IP, MSO_ADMIN, MSO_PASSWORD
except ImportError:
    sys.exit("Error: please verify credentials file format.")


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def runtime_error(msg):
    raise RuntimeError(msg)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="MSITE BD & EPG import")
    parser.add_argument('-sch', '--schema', required=True)
    parser.add_argument('-tmp', '--template', required=True)
    parser.add_argument('-anp', '--anp', required=True)
    parser.add_argument('-epg', '--endpoint_grpup', required=True)
    parser.add_argument('-bd', '--bridge_domain', required=True)
    parser.add_argument('-vrf', '--vrf_name', required=True)
    parser.add_argument('-vrf_t', '--vrf_template', required=True)
    parser.add_argument('-net', '--subnet', required=False)
    parser.add_argument('-d', '--deploy', default=False, action="store_true")
    parser.add_argument('-del', '--delete', default=False, action="store_true")
    args = parser.parse_args()

    schema = args.schema
    templateName = args.template
    anpName = args.anp
    epgName = args.endpoint_grpup
    bdName = args.bridge_domain
    vrfName = args.vrf_name
    templateNameVrf = args.vrf_template
    subnet = args.subnet


    '''logger'''
    logging.basicConfig(level=logging.INFO)

    logfh = logging.FileHandler(os.path.join('log', 'create_epg.log'))
    logger = logging.getLogger('epg_bd')
    logger.addHandler(logfh)
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logfh.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    mso_ip = var.IP_MSO


    '''Login in MSO'''
    rc = msc.RestClient(MSO_IP, MSO_ADMIN, MSO_PASSWORD)
    if rc:
        logger.info("Login to MSO successfull")
    response = rc.get('/schemas')

    if response.status_code != 200:
        logger.error((f"Status-Message:{response.content}"))
        runtime_error(response.content)
    '''Check whether template exist and build dict displayname to name'''
    schema_item, response = mso.filter_class(response.json(), {'fclass' : 'schemas', 'attr' : 'displayName', 'value' : schema})
    if not schema_item:
        logger.error(f"Schema: {schema} not found")
        sys.exit()
    template_dict = mso.check_template_name(schema_item,templateName)
    mso.check_template_name(schema_item, templateNameVrf)
    '''Check whether template is streched or site local Result True or False'''
    stretched_template, siteId = mso.template_streched_check(schema_item, template_dict[templateName])

    ''' if delete flag is true delete '''
    ''' Search if object has a reference  in site level. If true delete it first.'''

    if args.delete:
        template_site_ref,site_ref_item = mso.template_site_ref_check(template_dict[templateName], schema_item, "bds", bdName, "bdRef")
        if template_site_ref:
           for siteId_item in siteId:
               bd_obj = mso.bd(**{"bdName": bdName})
               bd_obj.delete(f"/sites/{siteId_item}-{template_dict[templateName]}/bds/{bdName}")
               body_del_bd = bd_obj.__dict__
               response = rc.patch(f"/schemas/{schema_item['id']}", **{"json_body": [body_del_bd]})

               if response.status_code != 200:
                  logger.error(response.content)
               else:
                  logger.info(f"Delete BD {bdName} site local config for site {siteId_item} successfull")
                  logger.debug(response.content)


        """ Delete Template config for bd and epg"""
        epg_obj = mso.epg(**{"epgName" : epgName})
        epg_obj.delete(f"/templates/{template_dict[templateName]}/anps/{anpName}/epgs/{epgName}")
        body_del_epg = epg_obj.__dict__
        response = rc.patch(f"/schemas/{schema_item['id']}", **{"json_body": [body_del_epg]})

        if response.status_code != 200:
            logger.error(response.content)
        else:
            logger.info(f"Delete EPG {epgName} successfull")
            logger.debug(response.content)

        bd_obj = mso.bd(**{"bdName": bdName})
        bd_obj.delete(f"/templates/{template_dict[templateName]}/bds/{bdName}")
        body_del_bd = bd_obj.__dict__
        response = rc.patch(f"/schemas/{schema_item['id']}", **{"json_body": [body_del_bd]})

        if response.status_code != 200:
            logger.error(response.content)
        else:
            logger.info(f"Delete BD {bdName} successfull")
            logger.debug(response.content)

        ''''if delete flag is false configure '''
    else:

        '''Define BD Patch json body'''
        bd_obj = mso.bd(**{"bdName" : bdName, "stretched_template" : stretched_template, "subnet" : subnet})
        bd_obj.path = (f"/templates/{template_dict[templateName]}/bds/-")
        bd_obj.value['vrfRef'] = {"schemaId": schema_item['id'], "templateName": template_dict[templateNameVrf], "vrfName": vrfName}
        body_add_bd = bd_obj.__dict__
        '''Patch Template BDs'''
        response = rc.patch(f"/schemas/{schema_item['id']}", **{"json_body": [body_add_bd]})
        if response.status_code != 200:
            logger.error(response.content)
        else:
            logger.info(f"Add BD {bdName} successfull")
            logger.debug(response.content)

        ''' subnet site level configuration when template is not stretched'''
        if subnet and not stretched_template:
            bd_obj = mso.bd(**{"bdName": bdName, "stretched_template": stretched_template, "subnet": subnet})
            bd_obj.path = (f"/sites/{siteId[0]}-{template_dict[templateName]}/bds/-")
            bd_obj.value['bdRef'] = {"schemaId": schema_item['id'], "templateName": template_dict[templateName],"bdName": bdName}
            bd_obj.value['subnets'] = [{"ip": subnet, "scope": "public", "shared": False}]
            body_add_bd = bd_obj.__dict__
            response = rc.patch(f"/schemas/{schema_item['id']}", **{"json_body": [body_add_bd]})

            if response.status_code != 200:
                logger.error(response.content)
            else:
                logger.info(f"Add Subnet site local BD {bdName} {subnet} successfull")
                logger.debug(response.content)


        '''Define EPG Patch json body'''
        epg_obj = mso.epg(**{"epgName" : epgName})
        epg_obj.path = (f"/templates/{template_dict[templateName]}/anps/{anpName}/epgs/-")
        epg_obj.value['bdRef'] = {"schemaId": schema_item['id'], "templateName": template_dict[templateName], "bdName": bdName}
        epg_obj.value['vrfRef'] = {"schemaId": schema_item['id'], "templateName": template_dict[templateNameVrf], "vrfName": vrfName}
        body_add_epg = epg_obj.__dict__

        '''Patch Template EPGs'''
        response = rc.patch(f"/schemas/{schema_item['id']}", **{"json_body": [body_add_epg]})

        if response.status_code != 200:
            logger.error(response.content)
        else:
            logger.info(f"Add EPG {bdName} successfull")
            logger.debug(response.content)

    if args.deploy:
        logger.info(f"Deploying Template {template_dict[templateName]}")
        response = rc.get(f"/execute/schema/{schema_item['id']}/template/{template_dict[templateName]}")
        logger.info(response.content)

