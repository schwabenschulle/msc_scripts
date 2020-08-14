import requests
import re
import json

class migration:
    def __init__(self, **kwargs):
        targetSchemaId = kwargs.get('targetSchemaId', None)
        targetTemplateName = kwargs.get('targetTemplateName', None)
        self.anps = []
        self.bds = []
        self.targetSchemaId = targetSchemaId
        self.targetTemplateName = targetTemplateName


class epg:
    def __init__(self, **kwargs):
        epgName = kwargs.get('epgName', None)
        self.op = "add"
        self.path = ""
        self.value = {}
        self.value['name'] = epgName
        self.value['displayName'] = epgName
        self.value['contractRelationships'] = []

    def delete(self, path):
        self.op = "remove"
        self.path = (path)


class bd:
    def __init__(self, **kwargs):
        bdName = kwargs.get('bdName', None)
        stretched_template = kwargs.get('stretched_template', False)
        subnet = kwargs.get('subnet', None)
        self.op = "add"
        self.path = ""
        self.value = {}
        self.value['name'] = bdName
        self.value['displayName'] = bdName
        self.value['l2Stretch'] = False
        self.value['l2UnknownUnicast'] = "proxy"
        self.value['subnets'] = []
        self.value['intersiteBumTrafficAllow'] = False
        self.value['optimizeWanBandwidth'] = False


        if stretched_template:
            self.value['intersiteBumTrafficAllow'] = True
            self.value['optimizeWanBandwidth'] = True
            self.value['l2Stretch'] = True

        if subnet and stretched_template:
            self.value['subnets'] = [{"ip": subnet, "scope": "public", "shared": False}]
            self.value['intersiteBumTrafficAllow'] = False
            self.value['optimizeWanBandwidth'] = False

        if not subnet:
            self.value['l2UnknownUnicast'] = "flood"

    def delete(self, path):
        self.op = "remove"
        self.path = path

    def update(self, path):
        self.op = "replace"
        self.path = path



def login_mso(login, ip_mso):
    session  = requests.Session()
    response = session.post((f"https://{ip_mso}/api/v1/auth/login"), verify=False, json=login)
    bearer = response.json()["token"]
    session.headers.update({'Authorization' : (f"Bearer {bearer}") })
    return session, response

def query_class(session,mso_ip,url_suffix, filter):
    response = session.get ((f"https://{mso_ip}/{url_suffix}"), verify=False)
    data = response.json()
    try:
        if not filter:
            return data,response
        else:
            for item in data[filter['fclass']]:
                if re.search(filter['value'], item[filter['attr']]):
                    return item,response
            return None,response
    except:
        return None, response

def filter_class(data, filter):
    try:
        if not filter:
            return None,data
        else:
            for item in data[filter['fclass']]:

                if re.search(filter['value'], item[filter['attr']]):
                    return item, data
            return None,data
    except:
        return None,data



def patch_class(session, mso_ip, url_suffix, body):
    response = session.patch((f"https://{mso_ip}/{url_suffix}") , verify=False, json = body)
    data = response.json()
    return data, response

'''Check whether template exist and build dict displayname to name'''
def check_template_name(schema_item, template):
    template_dict = {}
    template_list = []
    template_found = False
    for template_item in schema_item['templates']:
        if template_item['displayName'] == template:
            template_found = True
        template_dict[template_item['displayName']] = template_item['name']
    if not template_found:
        for key, val in template_dict.items():
            template_list.append(key)
        raise RuntimeError(f"Template not found. Available templates {template_list}")
    return template_dict

def template_streched_check(schema_item, templateName):
    count = 0
    stretched_template = False
    siteId = []
    for site_item in schema_item['sites']:
        if site_item['templateName'] == templateName:
            count += 1
            siteId.append(site_item['siteId'])
    if count > 1:
        stretched_template = True
    return stretched_template, siteId

''' Search for site references in schema if exist'''

def template_site_ref_check(templateName, schema_item, class_object, object_name, reference):
    template_site_ref = False
    return_item = []
    for site_item in (schema_item['sites']):
        for site_item in site_item['bds']:
            if re.search((f".*{templateName}\/{class_object}\/{object_name}.*"), str(site_item[reference])):
                template_site_ref = True
                return_item.append(site_item)
    return template_site_ref, return_item