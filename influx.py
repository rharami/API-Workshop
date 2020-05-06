import getopt
import sys
import jsonpickle
import time
import datetime
import meraki
from influxdb_client import InfluxDBClient
from datetime import datetime
from pytz import timezone

def main():
	# Environmental variables - THIS IS THE ONLY SECTION YOU NEED TO MODIFY
	api_key = ''
	org_id = ''
	data_logging_tag = ''
	influx_org_id =''
	influx_url = ''
	influx_token = ''

	#initialize API key and controllers and monro specific variables
	dashboard = meraki.DashboardAPI(api_key = api_key, output_log= False)
	client = InfluxDBClient(url = influx_url, token = influx_token)
	write_api = client.write_api()

	#pull list of organization networks make a dict of networks containing the tag specified in data_logging_tag and its name
	networks_in_scope = {}
	try:
		networks = dashboard.networks.getOrganizationNetworks(org_id)
	except meraki.APIError as e:
		print(f'Meraki API error: {e}')
	except Exception as e:
		print(f'some other error: {e}')

	for net in networks:
		if net['tags'] == None:
			continue
		elif data_logging_tag in net['tags']:
			networks_in_scope.update({net['id'] : net['name']})
		else:
			continue
	
	count = 0
	while count <= 40:
		data_to_db = []

		#get organizations uplink loss and latency - pulls all active MXs
		try:
			org_lantency_loss = dashboard.organizations.getOrganizationUplinksLossAndLatency(organizationId = org_id, timespan = 60)
		except meraki.APIError as e:
			print(f'Meraki API error: {e}')
		except Exception as e:
			print(f'some other error: {e}')

		#get performance score for each MX, security events etc in a network that had the logging tag, and build the database write sequence
		if org_lantency_loss:
			for network in org_lantency_loss:
				#check to see if the network has the logging tag
				if network['networkId'] in networks_in_scope.keys():

					net_name = networks_in_scope.get(network['networkId']).replace(" ","")
					uplink = network['uplink']
					latency = network['timeSeries'][0]['latencyMs']
					loss =  network['timeSeries'][0]['lossPercent']

					data_to_db.append(f"{net_name},wan={uplink} latency={latency}")
					data_to_db.append(f"{net_name},wan={uplink} loss={loss}")

					#get the MX performance score
					try:
						perf_score = dashboard.devices.getNetworkDevicePerformance(networkId = network['networkId'], serial = network['serial'])
					except meraki.APIError as e:
						print(f'Meraki API error: {e}')
					except Exception as e:
						print(f'some other error: {e}')

					perfscore = perf_score['perfScore']
					data_to_db.append(f"{net_name} perf_score={perfscore}")

					#get security events from MX
					try:
						net_sec_events = dashboard.security_events.getNetworkSecurityEvents(networkId = network['networkId'], timespan = 3600)
					except meraki.APIError as e:
						print(f'Meraki API error: {e}')
					except Exception as e:
						print(f'some other error: {e}')
				
					num_sec_events = len(net_sec_events)
					data_to_db.append(f"{net_name} sec_events={num_sec_events}")
				else:
					continue
		
		#Loop through networks in scope
		for net_id in networks_in_scope.keys():
			# get wireless health events for last hour
			net_name = networks_in_scope.get(net_id).replace(" ","")
			try:
				mr_health_events = dashboard.wireless_health.getNetworkFailedConnections(networkId = net_id, timespan = 3600)
			except meraki.APIError as e:
				print(f'Meraki API error: {e}')
			except Exception as e:
				print(f'some other error: {e}')

			if mr_health_events:
				num_mr_events = float(len(mr_health_events))
			else:
				num_mr_events = float(0)
			
			data_to_db.append(f"{net_name} wififails={num_mr_events}")

			#get date of last change in the change log
			try:
				last_change_details = dashboard.change_log.getOrganizationConfigurationChanges(organizationId = org_id, networkId = net_id)
			except meraki.APIError as e:
				print(f'Meraki API error: {e}')
			except Exception as e:
				print(f'some other error: {e}')

			#get timezone of network
			try:
				time_zone = dashboard.networks.getNetwork(net_id)
			except meraki.APIError as e:
				print(f'Meraki API error: {e}')
			except Exception as e:
				print(f'some other error: {e}')

			last_change_time = last_change_details[0]['ts']
			last_change_name = last_change_details[0]['adminName']
			conv_time = datetime.strptime(last_change_time, "%Y-%m-%dT%H:%M:%S.%fZ")
			conv_time_utc = conv_time.replace(tzinfo=timezone('UTC'))
			conv_time_translated = conv_time_utc.astimezone(timezone(time_zone['timeZone']))
			output_time = conv_time_translated.strftime("%b %d, %Y - %I:%M %p")

			data_to_db.append(f'{net_name} lastchange="{output_time} - {last_change_name}"')

		#write the data we have gathered to the database
		write_api.write("meraki", influx_org_id, data_to_db)
		
		#wait 15 seconds before gathering the next set of data
		time.sleep(15)

		#increment counter so the script will only run for 10 min at a time
		count += 1

if __name__ == '__main__':
	main()