#!/usr/bin/env python3
"""
Network debugging script to check connectivity to ansible-lint service
"""
import socket
import requests
import subprocess
import sys

def check_dns_resolution():
    """Check if we can resolve the hostname"""
    hostname = "lint-api-route-convert2ansible.apps.prod.rhoai.rh-aiservices-bu.com"
    print(f"🔍 Testing DNS resolution for: {hostname}")
    
    try:
        ip = socket.gethostbyname(hostname)
        print(f" DNS resolution successful: {hostname} -> {ip}")
        return True, ip
    except socket.gaierror as e:
        print(f" DNS resolution failed: {e}")
        return False, None

def check_ping(hostname):
    """Check if we can ping the host"""
    print(f"🏓 Testing ping to: {hostname}")
    try:
        result = subprocess.run(['ping', '-c', '3', hostname], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f" Ping successful")
            return True
        else:
            print(f" Ping failed: {result.stderr}")
            return False
    except Exception as e:
        print(f" Ping error: {e}")
        return False

def check_http_connectivity():
    """Check HTTP connectivity to the service"""
    url = "https://lint-api-route-convert2ansible.apps.prod.rhoai.rh-aiservices-bu.com/v1/lint/basic"
    print(f"🌐 Testing HTTP connectivity to: {url}")
    
    try:
        # Simple GET request first
        response = requests.get(url, timeout=10)
        print(f" HTTP GET successful: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError as e:
        print(f" HTTP connection failed: {e}")
        return False
    except requests.exceptions.Timeout as e:
        print(f" HTTP timeout: {e}")
        return False
    except Exception as e:
        print(f" HTTP error: {e}")
        return False

def check_vpn_status():
    """Check if VPN might be interfering"""
    print("🔒 Checking for VPN interference...")
    
    # Check if common VPN interfaces exist
    try:
        result = subprocess.run(['ifconfig'], capture_output=True, text=True)
        output = result.stdout.lower()
        
        vpn_indicators = ['tun', 'tap', 'utun', 'ppp']
        found_vpn = []
        
        for indicator in vpn_indicators:
            if indicator in output:
                found_vpn.append(indicator)
        
        if found_vpn:
            print(f"⚠️  Possible VPN interfaces detected: {found_vpn}")
            print("   This might be blocking access to the service")
            return True
        else:
            print(" No obvious VPN interfaces detected")
            return False
    except Exception as e:
        print(f"⚠️  Could not check VPN status: {e}")
        return False

def test_with_curl():
    """Test with curl command"""
    print("🔧 Testing with curl...")
    
    curl_cmd = [
        'curl', '-v', '--connect-timeout', '10',
        'https://lint-api-route-convert2ansible.apps.prod.rhoai.rh-aiservices-bu.com/v1/lint/basic'
    ]
    
    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print(" curl successful")
            print(f"Response: {result.stdout[:200]}...")
            return True
        else:
            print(f" curl failed:")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f" curl error: {e}")
        return False

def main():
    print("🚀 Starting network diagnostics for ansible-lint service")
    print("=" * 60)
    
    hostname = "lint-api-route-convert2ansible.apps.prod.rhoai.rh-aiservices-bu.com"
    
    # Step 1: DNS resolution
    dns_ok, ip = check_dns_resolution()
    print()
    
    # Step 2: Ping test (if DNS worked)
    if dns_ok:
        ping_ok = check_ping(hostname)
        print()
    else:
        ping_ok = False
    
    # Step 3: HTTP connectivity
    http_ok = check_http_connectivity()
    print()
    
    # Step 4: VPN check
    vpn_detected = check_vpn_status()
    print()
    
    # Step 5: curl test
    curl_ok = test_with_curl()
    print()
    
    # Summary
    print("📋 DIAGNOSIS SUMMARY")
    print("=" * 30)
    print(f"DNS Resolution: {'' if dns_ok else ''}")
    print(f"Ping Test: {'' if ping_ok else ''}")
    print(f"HTTP Connectivity: {'' if http_ok else ''}")
    print(f"VPN Detected: {'⚠️ ' if vpn_detected else ''}")
    print(f"Curl Test: {'' if curl_ok else ''}")
    
    if not dns_ok:
        print("\n🔧 RECOMMENDED FIXES:")
        print("1. Check your internet connection")
        print("2. Try changing DNS servers (8.8.8.8, 1.1.1.1)")
        print("3. Flush DNS cache: sudo dscacheutil -flushcache")
        print("4. Check if corporate firewall/proxy is blocking")
        print("5. Try connecting from different network")
    
    if vpn_detected:
        print("\n🔧 VPN-RELATED FIXES:")
        print("1. Try disconnecting VPN temporarily")
        print("2. Check VPN split-tunneling settings")
        print("3. Add the hostname to VPN bypass list")

if __name__ == "__main__":
    main()