#!/bin/bash

# Check if destination folder argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <destination_folder>"
    exit 1
fi

# Set destination folder from argument
DEST_BASE="$1"

# Ensure the destination directory exists
mkdir -p "$DEST_BASE"

# Configuration file
CONFIG_FILE="$(dirname "$0")/../config/connections.ini"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: connections.ini not found! Please create it from connections.ini.example."
    exit 1
fi

# Prompt for user input
echo -e "Experimenter (usually your initials): \c "
read experimenter
echo -e "Date (yyyymmdd): \c "
read date
echo -e "Experiment number (e.g. 01 or 12): \c "
read exp_num

# Define folder and path variables
folder="${date}_e${exp_num}"
path="Desktop/Behavior/${experimenter}/"

# Create experiment-specific subdirectories inside destination
DEST_PATH="${DEST_BASE}/${folder}/01_picams/01_raw"
mkdir -p "$DEST_PATH"

# Read and process each line in the configuration file
while IFS=' ' read -r identifier rest; do
    if [[ "$identifier" == "["* ]] || [[ -z "$identifier" ]]; then
        # Skip section headers and empty lines
        continue
    fi
    
    # Extract parameters using regex
    ip=$(echo "$rest" | grep -oP 'ansible_host=\K[0-9.]+')
    port=$(echo "$rest" | grep -oP 'ansible_port=\K[0-9]+')

    if [[ -n "$ip" && -n "$port" ]]; then
        echo "Fetching from $identifier ($ip) on port $port..."
        scp -P "$port" -r "pi@$ip:${path}${folder}_pic*/*.*" "$DEST_PATH"
        
        # Check if SCP was successful
        if [ $? -ne 0 ]; then
            echo "Error fetching from $identifier ($ip). Exiting."
            exit 1
        fi
    else
        echo "Invalid entry in $CONFIG_FILE: $identifier $rest"
    fi
done < "$CONFIG_FILE"

echo "All files have been successfully fetched and stored in $DEST_PATH"

