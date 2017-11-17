# Initial upgrade
sudo apt update
sudo apt upgrade

# Essential packages
sudo apt install python3-dev
sudo apt install python3-pip
sudo apt install python3-virtualenv
sudo apt install virtualenv
sudo apt install htop

# Create sudoer user
sudo adduser busboy
sudo adduser busboy sudo
su busboy.io
cd

# Change hostname
sudo vim /etc/hostname # busboy.io
sudo vim /etc/hosts # busboy.io

# Allow ssh access
sudo vim /etc/ssh/sshd_config #PasswordAuthentication yes
sudo service sshd restart
ssh-copy-id busboy@ip-address-of-server # From local
sudo vim /etc/ssh/sshd_config #PasswordAuthentication no
sudo service sshd restart
sudo reboot

# Set locales
export LC_ALL="en_US.UTF-8"
export LC_CTYPE="en_US.UTF-8"
sudo dpkg-reconfigure locales

# Setup repo
virtualenv -p python3 virtualenv
source virtualenv/bin/activate
git clone https://github.com/refik/busboy.io.git
pip install -r requirements.txt

# Configuration parameters
vim .Renviron # DB connection credentials & BUSBOY_DJANGO_PATH
echo "eval \`cat .Renviron | egrep '^SMP_.+=.+' | sed 's/.*/export &/'\`" >> .bash_profile
