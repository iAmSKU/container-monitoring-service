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
import logging

from MetrixUtil import *

logFilePathRoot = "/home/app/logs/CCReports/"
logFilePathRootBackup = "/home/app/logs/CCReportsBackup/"
characterList = ['/']
intervalInSecond = 3

logger = logging.getLogger(__name__)

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

    def FetchContainerStatistics(self):
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
        # print(statsObj)
        try:
            logFilePath = logFilePathRoot + containerName + ".log"
            file = open(logFilePath, "a")
            if not os.path.exists(logFilePath):
                statistics = "datetime,container-id,container-name,cpu-usages,memory-usages,memory-limit,memory-percentage,net-input,net-output,block-input,block-output,pid"
            else:
                r = self.stats(statsObj)
                # datetime
                statistics = statsObj['read'] + ","
                # container id
                statistics = statistics + statsObj['id'] + ","
                # container name
                statistics = statistics + self.trimCharacters(statsObj['name']) + ","
                # CPU usages
                statistics = statistics + r.get("cpu_percent") + ","
                # memory usages
                statistics = statistics + r.get("mem_current") + ","
                # memory limit
                statistics = statistics + r.get("mem_total") + ","
                # memory percentage
                statistics = statistics + r.get("mem_percent") + ","
                # net input
                statistics = statistics + r.get("net_rx") + ","
                # net output
                statistics = statistics + r.get("net_tx") + ","
                # block input
                statistics = statistics + r.get("blk_read") + ","
                # block output
                statistics = statistics + r.get("blk_write") + ","
                # PID
                statistics = statistics + str(statsObj['pids_stats']['current'])  
                            
            file.write(statistics + "\n")
            file.close()
            return True
        except Exception as newExp:
            print("Failed to write statistics.", newExp)
            return False

    def trimCharacters(self, input):
        for item in characterList:
                input = input.replace(item, '')
        return input
    
    def byteToMegaByte(self, input):
        input = input / (1024 * 1024)
        return str(input)
    
    def stats(self, x):
        cpu_total = 0.0
        cpu_system = 0.0
        cpu_percent = 0.0
        
        #for x in self.d.stats(self.container_id, decode=True, stream=True):
        blk_read, blk_write = calculate_blkio_bytes(x)
        net_r, net_w = calculate_network_bytes(x)
        mem_current = x["memory_stats"]["usage"]
        mem_total = x["memory_stats"]["limit"]

        try:
            cpu_percent, cpu_system, cpu_total = calculate_cpu_percent2(x, cpu_total, cpu_system)
        except KeyError as e:
            logger.error("error while getting new CPU stats: %r, falling back")
            cpu_percent = calculate_cpu_percent(x)

        r = {
            "cpu_percent": str(cpu_percent),
            "mem_current": self.byteToMegaByte(mem_current),
            "mem_total": self.byteToMegaByte(x["memory_stats"]["limit"]),
            "mem_percent": self.byteToMegaByte((mem_current / mem_total) * 100.0),
            "blk_read": self.byteToMegaByte(blk_read),
            "blk_write": self.byteToMegaByte(blk_write),
            "net_rx": self.byteToMegaByte(net_r),
            "net_tx": self.byteToMegaByte(net_w),
        }
        return r


if __name__ == "__main__":
    print("Inside main function")
    cMonitoring = ContainerMonitoring()

    # Setup initial structure
    if cMonitoring.Setup():
        print('Capturing container reports...')
        # Get the the running container from the predefined list
        cMonitoring.FetchContainerStatistics()
