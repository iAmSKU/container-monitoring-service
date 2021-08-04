import subprocess
import re
import time
import os
from datetime import datetime
import json
import threading
import tarfile
import csv
import signal
import sys

import docker

logFilePathRoot = "/home/app/logs/CCReports/"
logFilePathRootBackup = "/home/app/logs/CCReportsBackup/"
runningThread = True
characterList = ['/']


class ContainerMonitoring:

    def __init__(self):
        pass

    def Setup(self):
        print("Creating necessary folder structure...")
        try:
            # create a folder structure
            if not os.path.exists(logFilePathRoot):
                os.mkdir(logFilePathRoot)

            # create a backup folder structure
            if not os.path.exists(logFilePathRootBackup):
                os.mkdir(logFilePathRootBackup)

            # copy old files with new timestamp value and tar them
            oldDateTime = datetime.now().timestamp()
            for files in os.listdir(logFilePathRoot):
                # print(files)
                logFilePathRootBackupFile = logFilePathRootBackup + files + "." + str(oldDateTime) + ".tar"
                self.createBackup(logFilePathRootBackupFile, logFilePathRoot + files)
            return True

        except Exception as exp:
            print("Error: File is not exists or already removed, error reason", exp)
            return False

    def createBackup(self, output_filename, source_dir):
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))

    def FetchContainerStatistics(self, intervalInSecond):
        print("Inside FetchContainerStatistics...")
        containerDict = {}
        client = docker.from_env()
        try:
            while True:
                allContainerList = client.containers.list()
                index = 0
                while(index < len(allContainerList)):
                    try:
                        # get log file name
                        containerName = allContainerList[index].attrs['Name']
                        print("Writing log file for container:", self.trimCharacters(containerName))
                        stats = allContainerList[index].stats(stream=False)
                        if not self.writeContainerStatistics(containerName, stats):
                            print("Error while writing log statistics for container " + containerName)
                        time.sleep(intervalInSecond)
                    except Exception as newExp:
                        print("Unable to fetch statistics...reason:", newExp)
                    index = index + 1;
        except Exception as exp:
            print("Error while finding list of the docker container...reason:", exp)

    def writeContainerStatistics(self, containerName, statsObj):
        print("Inside writeContainerStatistics...")
        try:
            logFilePath = logFilePathRoot + containerName + ".log"
            file = open(logFilePath, "a")
            if not os.path.exists(logFilePath):
                statistics = "datetime,container-id,container-name,cpu-usages,memory-usages,memory-limit,memory-percentage,net-input,net-output,block-input,block-output,pid"
            else:
                statistics = statsObj['read'] + ","
                statistics = statistics + statsObj['id'] + ","
                statistics = statistics + self.trimCharacters(statsObj['name'])
            file.write(statistics + "\n")
            file.close()
            return True
        except Exception as newExp:
            print("Failed to write statistics.")
            return False

    def trimCharacters(self, input):
        for item in characterList:
                input = input.replace(item, '')
        return input


if __name__ == "__main__":
    print("Inside main function")
    cMonitoring = ContainerMonitoring()

    # Setup initial structure
    if cMonitoring.Setup():
        print('Capturing container reports...')
        # Get the the running container from the predefined list
        cMonitoring.FetchContainerStatistics(3)
