import random
import logging
import string
import os
import inspect
from shutit_module import ShutItModule

class shutit_ipsec_simple(ShutItModule):


	def build(self, shutit):
		# Destroy pre-existing, leftover vagrant images.
		shutit.run_script('''#!/bin/bash
MODULE_NAME=shutit_ipsec_simple
rm -rf $( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/vagrant_run/*
if [[ $(command -v VBoxManage) != '' ]]
then
	while true
	do
		VBoxManage list runningvms | grep ${MODULE_NAME} | awk '{print $1}' | xargs -IXXX VBoxManage controlvm 'XXX' poweroff && VBoxManage list vms | grep shutit_ipsec_simple | awk '{print $1}'  | xargs -IXXX VBoxManage unregistervm 'XXX' --delete
		# The xargs removes whitespace
		if [[ $(VBoxManage list vms | grep ${MODULE_NAME} | wc -l | xargs) -eq '0' ]]
		then
			break
		else
			ps -ef | grep virtualbox | grep ${MODULE_NAME} | awk '{print $2}' | xargs kill
			sleep 10
		fi
	done
fi
if [[ $(command -v virsh) ]] && [[ $(kvm-ok 2>&1 | command grep 'can be used') != '' ]]
then
	virsh list | grep ${MODULE_NAME} | awk '{print $1}' | xargs -n1 virsh destroy
fi
''')
		vagrant_image = shutit.cfg[self.module_id]['vagrant_image']
		vagrant_provider = shutit.cfg[self.module_id]['vagrant_provider']
		gui = shutit.cfg[self.module_id]['gui']
		memory = shutit.cfg[self.module_id]['memory']
		shutit.cfg[self.module_id]['vagrant_run_dir'] = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0))) + '/vagrant_run'
		run_dir = shutit.cfg[self.module_id]['vagrant_run_dir']
		module_name = 'shutit_ipsec_simple_' + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(6))
		this_vagrant_run_dir = run_dir + '/' + module_name
		shutit.cfg[self.module_id]['this_vagrant_run_dir'] = this_vagrant_run_dir
		shutit.send(' command rm -rf ' + this_vagrant_run_dir + ' && command mkdir -p ' + this_vagrant_run_dir + ' && command cd ' + this_vagrant_run_dir)
		shutit.send('command rm -rf ' + this_vagrant_run_dir + ' && command mkdir -p ' + this_vagrant_run_dir + ' && command cd ' + this_vagrant_run_dir)
		if shutit.send_and_get_output('vagrant plugin list | grep landrush') == '':
			shutit.send('vagrant plugin install landrush')
		shutit.send('vagrant init ' + vagrant_image)
		shutit.send_file(this_vagrant_run_dir + '/Vagrantfile','''Vagrant.configure("2") do |config|
  config.landrush.enabled = true
  config.vm.provider "virtualbox" do |vb|
    vb.gui = ''' + gui + '''
    vb.memory = "''' + memory + '''"
  end

  config.vm.define "ipsec1" do |ipsec1|
    ipsec1.vm.box = ''' + '"' + vagrant_image + '"' + '''
    ipsec1.vm.hostname = "ipsec1.vagrant.test"
    config.vm.provider :virtualbox do |vb|
      vb.name = "shutit_ipsec_simple_1"
    end
  end
  config.vm.define "ipsec2" do |ipsec2|
    ipsec2.vm.box = ''' + '"' + vagrant_image + '"' + '''
    ipsec2.vm.hostname = "ipsec2.vagrant.test"
    config.vm.provider :virtualbox do |vb|
      vb.name = "shutit_ipsec_simple_2"
    end
  end
end''')
		pw = shutit.get_env_pass()
		try:
			shutit.multisend('vagrant up --provider ' + shutit.cfg['shutit-library.virtualization.virtualization.virtualization']['virt_method'] + " ipsec1",{'assword for':pw,'assword:':pw},timeout=99999)
		except NameError:
			shutit.multisend('vagrant up ipsec1',{'assword for':pw,'assword:':pw},timeout=99999)
		if shutit.send_and_get_output("""vagrant status | grep -w ^ipsec1 | awk '{print $2}'""") != 'running':
			shutit.pause_point("machine: ipsec1 appears not to have come up cleanly")
		try:
			shutit.multisend('vagrant up --provider ' + shutit.cfg['shutit-library.virtualization.virtualization.virtualization']['virt_method'] + " ipsec2",{'assword for':pw,'assword:':pw},timeout=99999)
		except NameError:
			shutit.multisend('vagrant up ipsec2',{'assword for':pw,'assword:':pw},timeout=99999)
		if shutit.send_and_get_output("""vagrant status | grep -w ^ipsec2 | awk '{print $2}'""") != 'running':
			shutit.pause_point("machine: ipsec2 appears not to have come up cleanly")


		# machines is a dict of dicts containing information about each machine for you to use.
		machines = {}
		machines.update({'ipsec1':{'fqdn':'ipsec1.vagrant.test'}})
		ip = shutit.send_and_get_output('''vagrant landrush ls 2> /dev/null | grep -w ^''' + machines['ipsec1']['fqdn'] + ''' | awk '{print $2}' ''')
		machines.get('ipsec1').update({'ip':ip})
		machines.update({'ipsec2':{'fqdn':'ipsec2.vagrant.test'}})
		ip = shutit.send_and_get_output('''vagrant landrush ls 2> /dev/null | grep -w ^''' + machines['ipsec2']['fqdn'] + ''' | awk '{print $2}' ''')
		machines.get('ipsec2').update({'ip':ip})

		for machine in sorted(machines.keys()):
			shutit.login(command='vagrant ssh ' + machine)
			shutit.login(command='sudo su -',password='vagrant')
			root_password = 'root'
			shutit.install('net-tools') # netstat needed
			if not shutit.command_available('host'):
				shutit.install('bind-utils') # host needed
			# Workaround for docker networking issues + landrush.
			shutit.install('docker')
			shutit.insert_text('Environment=GODEBUG=netdns=cgo','/lib/systemd/system/docker.service',pattern='.Service.')
			shutit.send('mkdir -p /etc/docker',note='Create the docker config folder')
			shutit.send_file('/etc/docker/daemon.json',"""{
  "dns": ["8.8.8.8"]
}""",note='Use the google dns server rather than the vagrant one. Change to the value you want if this does not work, eg if google dns is blocked.')
			shutit.send('systemctl restart docker')
			shutit.multisend('passwd',{'assword:':root_password})
			shutit.send("""sed -i 's/.*PermitRootLogin.*/PermitRootLogin yes/g' /etc/ssh/sshd_config""")
			shutit.send("""sed -i 's/.*PasswordAuthentication.*/PasswordAuthentication yes/g' /etc/ssh/sshd_config""")
			shutit.send('service ssh restart || systemctl restart sshd')
			shutit.multisend('ssh-keygen',{'Enter':'','verwrite':'n'})
			shutit.logout()
			shutit.logout()
		for machine in sorted(machines.keys()):
			shutit.login(command='vagrant ssh ' + machine)
			shutit.login(command='sudo su -',password='vagrant')
			for copy_to_machine in machines:
				for item in ('fqdn','ip'):
					shutit.multisend('ssh-copy-id root@' + machines[copy_to_machine][item],{'assword:':root_password,'ontinue conn':'yes'})
			shutit.logout()
			shutit.logout()
		shutit.login(command='vagrant ssh ' + sorted(machines.keys())[0])
		shutit.login(command='sudo su -',password='vagrant')
		shutit.logout()
		shutit.logout()
		shutit.log('''Vagrantfile created in: ''' + this_vagrant_run_dir,add_final_message=True,level=logging.DEBUG)
		shutit.log('''Run:

	cd ''' + this_vagrant_run_dir + ''' && vagrant status && vagrant landrush ls

To get a picture of what has been set up.''',add_final_message=True,level=logging.DEBUG)

		# TODO: https://libreswan.org/wiki/Configuration_examples
		# TODO: https://libreswan.org/wiki/Host_to_host_VPN

serverleft
[root@west ~]# ipsec newhostkey --output /etc/ipsec.secrets
Generated RSA key pair using the NSS database
[root@west ~]# ipsec showhostkey --left
	# rsakey AQOrlo+hO
	leftrsasigkey=0sAQOrlo+hOafUZDlCQmXFrje/oZm [...] W2n417C/4urYHQkCvuIQ==
[root@west ~]# 


serverright
[root@east ~]# ipsec newhostkey --output /etc/ipsec.secrets
Generated RSA key pair using the NSS database
[root@east ~]# ipsec showhostkey --right
	# rsakey AQO3fwC6n
	rightrsasigkey=0sAQO3fwC6nSSGgt64DWiYZzuHbc4 [...] D/v8t5YTQ==


You should now have a file called /etc/ipsec.secrets on both sides, which contain the public component of the RSA key. The secret part is stored in /etc/ipsec.d/*.db files, also called the "NSS database". You can protect this database with a passphrase if you want, but it will prevent the machine from bringing up the tunnel on boot, as a human would need to enter the passphrase. Note that on older openswan versions compiled without HAVE_NSS, the /etc/ipsec.secret file actually contains the secret part of the rsa keypair as well.

Now we are ready to make a simple /etc/ipsec.conf file for our host to host tunnel. The leftrsasigkey/rightrsasigkey from above, are added to the configuration below.

# /etc/ipsec.conf
# The version 2 is only required for compatibility with openswan
version 2

config setup
    protostack=netkey

conn mytunnel
    leftid=@west
    left=192.1.2.23
    leftrsasigkey=0sAQOrlo+hOafUZDlCQmXFrje/oZm [...] W2n417C/4urYHQkCvuIQ==
    rightid=@east
    right=192.1.2.45
    rightrsasigkey=0sAQO3fwC6nSSGgt64DWiYZzuHbc4 [...] D/v8t5YTQ==
    authby=rsasig
    # use auto=start when done testing the tunnel
    auto=add



You can use the identical configuration file on both east and west. They will auto-detect if they are "left" or "right".

First, ensure ipsec is started:

ipsec setup start
Then ensure the connection loaded:

ipsec auto --add mytunnel
And then try and bring up the tunnel:

ipsec auto --up mytunnel
If all went well, you should see something like:

# ipsec auto --up  mytunnel
104 "mytunnel" #1: STATE_MAIN_I1: initiate
003 "mytunnel" #1: received Vendor ID payload [Dead Peer Detection]
003 "mytunnel" #1: received Vendor ID payload [FRAGMENTATION]
106 "mytunnel" #1: STATE_MAIN_I2: sent MI2, expecting MR2
108 "mytunnel" #1: STATE_MAIN_I3: sent MI3, expecting MR3
003 "mytunnel" #1: received Vendor ID payload [CAN-IKEv2]
004 "mytunnel" #1: STATE_MAIN_I4: ISAKMP SA established {auth=RSA_SIG cipher=aes_128 prf=sha group=MODP2048}
117 "mytunnel" #2: STATE_QUICK_I1: initiate
004 "mytunnel" #2: STATE_QUICK_I2: sent QI2, IPsec SA established tunnel mode {ESP=>0xESPESP<0xESPESP xfrm=AES_128-HMAC_SHA1 NATOA=none NATD=none DPD=passive}
If you want the tunnel to start when the machine starts, change "auto=add" to "auto=start". Also ensure that your system starts the ipsec service on boot. This can be done using the "service" or "systemctl" command, depending on the init system used for the server.




		return True


	def get_config(self, shutit):
		shutit.get_config(self.module_id,'vagrant_image',default='ubuntu/xenial64')
		shutit.get_config(self.module_id,'vagrant_provider',default='virtualbox')
		shutit.get_config(self.module_id,'gui',default='false')
		shutit.get_config(self.module_id,'memory',default='1024')
		shutit.get_config(self.module_id,'vagrant_run_dir',default='/tmp')
		shutit.get_config(self.module_id,'this_vagrant_run_dir',default='/tmp')
		return True

	def test(self, shutit):
		return True

	def finalize(self, shutit):
		return True

	def is_installed(self, shutit):
		return False

	def start(self, shutit):
		return True

	def stop(self, shutit):
		return True

def module():
	return shutit_ipsec_simple(
		'imiell.shutit_ipsec_simple.shutit_ipsec_simple', 720849744.0001,
		description='',
		maintainer='',
		delivery_methods=['bash'],
		depends=['shutit.tk.setup','shutit-library.virtualization.virtualization.virtualization','tk.shutit.vagrant.vagrant.vagrant']
	)
