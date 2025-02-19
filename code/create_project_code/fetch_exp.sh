#!/bin/bash

# Configuration file
CONFIG_FILE="connections.ini"

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

# Create local directories
dest_base="$HOME/Desktop/${folder}/01_picams/01_raw"
mkdir -p "$dest_base"

# Read and process each line in the configuration file
while IFS=': ' read -r identifier ip port; do
    if [[ -n "$identifier" && -n "$ip" && -n "$port" ]]; then
        echo "Fetching from $identifier ($ip) on port $port..."
        scp -P "$port" -r "pi@$ip:${path}${folder}_pic*/*.*" "$dest_base"
    else
        echo "Invalid entry in $CONFIG_FILE: $identifier $ip $port"
    fi
done < "$CONFIG_FILE"

echo "All files have been fetched and stored in $dest_base"

