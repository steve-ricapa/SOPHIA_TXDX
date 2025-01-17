import json
import meraki

def listar_organizaciones_y_redes(api_key, output_file="organizations_and_networks.json"):
    """
    Lista las organizaciones disponibles y sus redes automáticamente.
    Guarda los datos en un archivo JSON en la misma carpeta y retorna la lista de organizaciones con redes.

    :param api_key: Clave de API de Meraki
    :param output_file: Nombre del archivo JSON donde se guardarán los datos (opcional)
    :return: Lista de organizaciones con sus redes
    """
    dashboard = meraki.DashboardAPI(api_key)
    try:
        # Listar todas las organizaciones
        orgs = dashboard.organizations.getOrganizations()
        print("Organizaciones disponibles:")
        organizaciones = []

        for org in orgs:
            print(f"- {org['name']} (ID: {org['id']})")

            # Listar las redes de la organización
            networks = dashboard.organizations.getOrganizationNetworks(org['id'])
            print(f"Redes disponibles en la organización {org['name']}:")
            redes = []
            for net in networks:
                print(f"  - {net['name']} (ID: {net['id']})")
                redes.append({
                    "network_id": net['id'],
                    "name": net['name']
                })
            organizaciones.append({
                "org_id": org['id'],
                "name": org['name'],
                "networks": redes
            })

        # Guardar la información en un archivo JSON
        with open(output_file, "w") as json_file:
            json.dump(organizaciones, json_file, indent=2)

        print(f"\nSe ha guardado la información en '{output_file}'.")
        return organizaciones

    except meraki.APIError as e:
        print(f"Error en la API de Meraki: {e.message}")
        return []
    except Exception as e:
        print(f"Error inesperado: {e}")
        return []


def obtener_datos_red(api_key, org_id, network_id, output_file="network_data.json"):
    """
    Obtiene información detallada de una red específica y la guarda en un archivo JSON.

    :param api_key: Clave de API de Meraki.
    :param org_id: ID de la organización.
    :param network_id: ID de la red.
    :param output_file: Nombre del archivo JSON donde se guardarán los datos (opcional).
    :return: Diccionario con la información de la red.
    """
    # Crear el objeto DashboardAPI
    dashboard = meraki.DashboardAPI(api_key, log_path=None)
    network_data = {}

    try:
        # Obtener estado de los dispositivos en la red
        devices = dashboard.networks.getNetworkDevices(network_id)
        devices_status = []
        for device in devices:
            status = dashboard.devices.getDevice(device['serial'])
            devices_status.append({
                "name": device.get("name", "N/A"),
                "model": device.get("model", "N/A"),
                "serial": device.get("serial", "N/A"),
                "firmware": device.get("firmware", "N/A"),
                "connection_status": status.get("status", "unknown"),
                "uptime": status.get("uptime", "N/A"),
                "ports_status": status.get("portStatus", "N/A")
            })
        network_data['devices_status'] = devices_status

        # Listar clientes conectados a los puntos de acceso
        clients = dashboard.networks.getNetworkClients(network_id, total_pages="all")
        clients_data = []
        for client in clients:
            clients_data.append({
                "ip": client.get("ip", "N/A"),
                "description": client.get("description", "N/A"),
                "ssid": client.get("ssid", "N/A"),
                "uptime": client.get("uptime", "N/A"),
                "usage": client.get("usage", {})
            })
        network_data['clients_data'] = clients_data

        # Obtener reglas de firewall de un dispositivo MX
        firewall_rules = dashboard.appliance.getNetworkApplianceFirewallL3FirewallRules(network_id)
        network_data['firewall_rules'] = firewall_rules

        # Listar VLANs configuradas en la red
        vlans = dashboard.appliance.getNetworkApplianceVlans(network_id)
        network_data['vlans'] = vlans

        # Listar SSIDs configurados en los puntos de acceso
        ssids = dashboard.wireless.getNetworkWirelessSsids(network_id)
        ssid_data = []
        for ssid in ssids:
            ssid_data.append({
                "name": ssid.get("name", "N/A"),
                "enabled": ssid.get("enabled", "N/A"),
                "bandwidth_limit": ssid.get("bandwidthLimit", {}).get("limitUp", "N/A")
            })
        network_data['ssids'] = ssid_data

        # Últimos eventos registrados en la red
        # events = dashboard.networks.getNetworkEvents(network_id, total_pages="all", productType="wireless")
        # network_data['events'] = events



        # Guardar la información en un archivo JSON
        with open(output_file, "w") as json_file:
            json.dump(network_data, json_file, indent=2)

        print(f"\nSe ha guardado la información de la red en '{output_file}'.")
        return network_data

    except meraki.APIError as e:
        print(f"Error en la API de Meraki: {e.message}")
        return {}
    except Exception as e:
        print(f"Error inesperado: {e}")
        return {}
