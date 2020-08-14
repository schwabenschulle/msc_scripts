Python 3 Code

**COMMON**
This tiny SDK for MSC rest handling is used
https://github.com/datacenter/multisiteOrchestratorPython?fbclid=IwAR3VRv5zEheB9uDJfuGUpE5aRdJWLZZFNTs5wrV4TXpG72GdYXO8DPqkTS4

**Example add-epg-bd**
python add-epg-bd.py -d -sch CCST-P-T -tmp LAB11-LAB12 -anp GROUP-B_ANP -epg NEWEPG_V3020_EPG -bd NEWEPG_V3020_BD -vrf CCST_1_VRF -vrf_t LAB11-LAB12 -del


-d - deploy - needed for add and delete. It push the change to APIC

-del - delete

-sch CCST-P-T Schema it's the tenant name

-tmp LAB11 or LAB12 or LAB11-LAB12 - site local vs. streched template 

-anp GROUP-B_ANP 

-epg NEWEPG_V3020_EPG

-bd NEWEPG_V3020_BD

-vrf CCST_1_VRF

-vrf_t LAB11-LAB12 - Template of the vrf will improve it. Vrf name is unique so can find where the object is

**Example migration**

With MSC a couple of new term have been introduced. 

-site - A site is ACI Fabric which his managed by MSC

-schema - a schema is an construct which has a 1:1 relation to a ACI Tenant. e.g. CCST_P_T is the schema in MSC which
          represent the CCST_P_T Tenant from LAB11 Fabric
          
-Template - A Template is a logical construct which allows us to control which object get programmed in particular sites              


**Function of Migration script**

This this script manage the need to migrate EPG BD from one Template to another.
e.g 
Template LAB11 held site local object for site LAB11
Template LAB12 held aite local object for site LAB12
Template LAB13 held site local object for site LAB13
Template LAB11-LAB12-LAB13 held objects which are streched over all sits.

Example1: We migrate in Schema CCST_P_T (-sch ) from source Template (-s_tmp) to target tempplate (-t_tmp LAB11-LAB12-LAB13)
          the EPG (-epg) GROUP-B_V2011_EPG and (-bd) GROUP-B_V2011_BD.
          This is a migration from a site local to a streched template. A steched template is a template which is assigned
          to more then 1 site. It is important to manage to know is it a migration from site-local template to strech or other
          way around or maybe between 2 site local template. When we migrate to stretched template the subnet needs to 
          be deleted in site local object and added in template section of the configuration. L3Outs needs to configured
          on any site config section where the template is assigned to. Further more we change parameters in BD like
          L2strech, intersiteBumTraffic, intersiteBumTrafficAllow and optimizeWanBandwidth. 

(py36) rcf8fe@FE-Z1TNY:~/PycharmProjects/svs-mso$ python migrate_epg_bd.py -sch CCST_P_T -s_tmp LAB11 -t_tmp LAB11-LAB12-LAB13 -bd GROUP-B_V2011_BD -epg GROUP-B_V2011_EPG -anp GROUP-B_ANP -d
INFO:migrate_epg_bd:Login to MSO
INFO:migrate_epg_bd:Getting Schema ID
INFO:migrate_epg_bd:Sending PUT Call to MSO
INFO:migrate_epg_bd:Migration GROUP-B_V2011_EPG from LAB11 to LAB11-LAB12-LAB13 successfull
INFO:migrate_epg_bd:Lookup for Object GROUP-B_V2011_BD which is supposed to be stretched
INFO:migrate_epg_bd:Migrate Subnets {'ip': '10.116.97.33/27', 'description': '', 'scope': 'public', 'shared': False} for site-local to template LAB11-LAB12-LAB13
INFO:migrate_epg_bd:Migrate Subnets {'ip': '2a03:cc00:16:2011::33/64', 'description': '', 'scope': 'public', 'shared': False} for site-local to template LAB11-LAB12-LAB13
INFO:migrate_epg_bd:Collect L3OUT ['OSPF_AREA_1.1.1.1_L3OUT'] from all sites
INFO:migrate_epg_bd:Removing Subnets from Site-Level
INFO:migrate_epg_bd:Schema Update successfull
INFO:migrate_epg_bd:Update Site-ID  5f310306360000936d8e79ea L3OUT ['OSPF_AREA_1.1.1.1_L3OUT'] successfull
INFO:migrate_epg_bd:Update Site-ID  5f3105d3360000fc82e9aa68 L3OUT ['OSPF_AREA_1.1.1.1_L3OUT'] successfull
INFO:migrate_epg_bd:Update Site-ID  5f3103ba360000b76d8e79ec L3OUT ['OSPF_AREA_1.1.1.1_L3OUT'] successfull
INFO:migrate_epg_bd:Deploying Target Template LAB11-LAB12-LAB13
INFO:migrate_epg_bd:b'{"msg":"Successfully deployed"}'
INFO:migrate_epg_bd:Deploying Source Template LAB11
INFO:migrate_epg_bd:b'{"msg":"Successfully deployed"}'

**Example Migration stretched template to site local template**

(py36) rcf8fe@FE-Z1TNY:~/PycharmProjects/svs-mso$ python migrate_epg_bd.py -sch CCST_P_T -s_tmp LAB11-LAB12-LAB13 -t_tmp LAB11 -bd GROUP-B_V2011_BD -epg GROUP-B_V2011_EPG -anp GROUP-B_ANP -d
INFO:migrate_epg_bd:Login to MSO
INFO:migrate_epg_bd:Getting Schema ID
INFO:migrate_epg_bd:Sending PUT Call to MSO
INFO:migrate_epg_bd:Migration GROUP-B_V2011_EPG from LAB11-LAB12-LAB13 to LAB11 successfull
INFO:migrate_epg_bd:Lookup for Object GROUP-B_V2011_BD which is supposed to be stretched
INFO:migrate_epg_bd:Add Subnets to Site-Level
INFO:migrate_epg_bd:Schema Update successfull
INFO:migrate_epg_bd:Update Template Subnet successfull
INFO:migrate_epg_bd:Deploying Target Template LAB11
INFO:migrate_epg_bd:b'{"msg":"Successfully deployed"}'
INFO:migrate_epg_bd:Deploying Source Template LAB11-LAB12-LAB13
INFO:migrate_epg_bd:b'{"msg":"Successfully deployed"}'


**Personal Notes** 

JSON to print pretty e.g. 
print (json.dumps(schema_item['sites'], sort_keys=True, indent=2, separators=(',', ':')))


GEt include 
GET /api/v1/schemas/583c7c482501002501061985?include=**health,faults,status,associations,references,policy-states**