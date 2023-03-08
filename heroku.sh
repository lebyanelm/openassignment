#!/usr/bin/env bash

# Adding some colors to the output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Help text
usage="
A quick program to add multiple config variables to the heroku server. Following options are required:
  -h,  [--help]    | show this help text
  -f=, [--file=]   | path of the file to read the variables from
  -s=, [--server=] | name of the heroku server to add the variable to
  -k=, [--keys=]   | space seperated keys to be added to the config variables
Sample command: ./$(basename "$0") -f='/path/to/your/.environment/file' -s='bsc-server-name' -k='YOUR_CONFIG_KEY1 YOUR_CONFIG_KEY2'
"

# Reading input options
for i in "$@"; do
  case $i in
    -f=*|--file=*)
      FILE="${i#*=}"
    ;;

    -s=*|--server=*)
      SERVER="${i#*=}"
    ;;

    -k=*|--keys=*)
      var="${i#*=}"
      KEYS=($var)
    ;;

    -h*|--help*)
      printf "$usage"
      exit 0
    ;;

    *)
      # ignoring unknown option
    ;;
  esac
done

# Check if -f option is present
if [ -z $FILE ]
then
  echo -e "\n${YELLOW}--file${NC} ${RED}option missing${NC}. Use --help option to know the command\n"
  exit 1
fi

# Check if -s option is present
if [ -z $SERVER ]
then
  echo -e "\n${YELLOW}--server${NC} ${RED}option missing${NC}. Use --help option to know the command\n"
  exit 1
fi

# Check if -k option is present
if [ -z $KEYS ]
then
  echo -e "\n${YELLOW}--keys${NC} ${RED}option missing${NC}. Use --help option to know the command\n"
  exit 1
fi

# Confirming the server name and restart scenario from the user
read -p "$(echo -e Are you sure to add variables to ${BLUE}$SERVER${NC} server? It will ${RED}Restart on every variable..${NC} - Yes/No \> ) " choice

case "$choice" in
  [yY][eE][sS])
    echo -e "\n${GREEN}Alright buddy!!!${NC}\n"
    for key in "${KEYS[@]}"; do
      # Reading values for the provided keys from yaml file
      value=$(echo `grep -w -A0 $key $FILE | tail -n1 | awk '{print $2}'` | tee)
      if [ -z $value ]
      then
        # Display error if value not found
        echo -e "${YELLOW}$key ${RED}not found..${NC}\n"
        continue
      else
        # Set heroku config var if value found
        heroku config:set $key=$value -a $SERVER
        echo
      fi
    done
  ;;
  [nN][oO])
    echo -e "\n${YELLOW}Okay, exiting..${NC}"
  ;;
  *)
    echo -e "\n${RED}Invalid input..${NC}"
  ;;
esac
