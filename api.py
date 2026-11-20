import ipaddress
from flask import Flask, render_template, request
from netmiko import ConnectHandler

app = Flask(__name__)

ROUTER_DEVICE = {
    'device_type': 'cisco_ios_telnet',
    'ip': '192.168.10.227',
    'port': 32770,
    'username': 'admin',
    'password': 'eve123',
    'secret': 'eve123',
}

COMMANDS_TO_RUN = [
    "show version",
    "show ip interface brief",
    "show running-config",
]


def validate_ipv4(value, label):
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        raise ValueError(f"Invalid {label}: '{value}'")


def validate_mask(value):
    try:
        ipaddress.IPv4Network(f"0.0.0.0/{value}")
    except ValueError:
        raise ValueError(f"Invalid Subnet Mask: '{value}'")


def push_config(config_lines, save_config):
    with ConnectHandler(**ROUTER_DEVICE) as net_connect:
        net_connect.enable()
        output = net_connect.send_config_set(config_lines)
        if save_config:
            output += "\n" + net_connect.save_config()
        return output


@app.route("/", methods=["GET", "POST"])
def index():
    results = {}
    config_output = None
    error = None
    active_tab = "dashboard"

    if request.method == "POST":
        action = request.form.get("action", "show")
        save_config = request.form.get("save_config") == "on"

        try:
            if action == "config_interface":
                active_tab = "config"
                interface = request.form.get("interface", "").strip()
                ip_addr = request.form.get("ip_address", "").strip()
                mask = request.form.get("subnet_mask", "").strip()
                description = request.form.get("description", "").strip()
                status = request.form.get("status", "no shutdown")

                if not interface:
                    raise ValueError("Interface name is required.")
                validate_ipv4(ip_addr, "IP Address")
                validate_mask(mask)

                config_lines = [
                    f"interface {interface}",
                    f"ip address {ip_addr} {mask}",
                ]
                if description:
                    config_lines.append(f"description {description}")
                config_lines.append("shutdown" if status == "shutdown" else "no shutdown")

                config_output = push_config(config_lines, save_config)

            elif action == "config_device":
                active_tab = "config"
                hostname = request.form.get("hostname", "").strip()
                banner = request.form.get("banner", "").strip()

                config_lines = []
                if hostname:
                    if " " in hostname:
                        raise ValueError("Hostname cannot contain spaces.")
                    config_lines.append(f"hostname {hostname}")
                if banner:
                    clean_banner = banner.replace("#", "")
                    config_lines.append(f"banner motd #{clean_banner}#")

                if not config_lines:
                    raise ValueError("Enter a hostname or banner to update.")

                config_output = push_config(config_lines, save_config)

            elif action == "config_route":
                active_tab = "config"
                dest_network = request.form.get("dest_network", "").strip()
                route_mask = request.form.get("route_mask", "").strip()
                next_hop = request.form.get("next_hop", "").strip()

                validate_ipv4(dest_network, "Destination Network")
                validate_mask(route_mask)
                if not next_hop:
                    raise ValueError("Next-Hop IP or exit interface is required.")

                config_lines = [f"ip route {dest_network} {route_mask} {next_hop}"]
                config_output = push_config(config_lines, save_config)

            else:
                active_tab = "dashboard"
                with ConnectHandler(**ROUTER_DEVICE) as net_connect:
                    net_connect.enable()
                    for cmd in COMMANDS_TO_RUN:
                        results[cmd] = net_connect.send_command(cmd)

        except Exception as e:
            error = str(e)

    return render_template(
        "index.html",
        results=results,
        config_output=config_output,
        error=error,
        active_tab=active_tab,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)