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
invalidCharList = ['%', 'MB', 'GB', 'MiB', 'GiB', 'B', 'k']
allThread = []
runningThread = True

class ContainerMonitoring:
    dockerContainerList = ['cloud-connector-device-adapter',
                           'sim-edge-event-publisher',
                           'cloud-connector-watcher-service',
                           'sim-edge-service-mindsphere-native',
                           'sim-edge-system-app-s7-service',
                           'redis']
    requiredContainerDict = {}

    def __init__(self):
        pass

    def setup(self):
        try:
            #create a folder structure
            if not os.path.exists(logFilePathRoot):
                os.mkdir(logFilePathRoot)

            #create a backup folder structure
            if not os.path.exists(logFilePathRootBackup):
                os.mkdir(logFilePathRootBackup)

            #copy old files with new timestamp value and tar them
            oldDateTime = datetime.now().timestamp()
            for files in os.listdir(logFilePathRoot):
                #print(files)
                logFilePathRootBackupFile = logFilePathRootBackup + files + "." + str(oldDateTime) + ".tar"
                self.createBackup(logFilePathRootBackupFile, logFilePathRoot+files)

        except Exception as exp:
            print("File is not exists or already removed!")

    def createBackup(self, output_filename, source_dir):
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))

    def getRunningContainer(self):
        print("Inside getRunningContainer...")
        containerDict = {}
        client = docker.from_env()
        try:
            print("Container List:", client.container.list)
            allContainerList = subprocess.Popen(['docker', 'ps'], stdout=subprocess.PIPE)
            index = 0
            while True:
                line = allContainerList.stdout.readline()
                if not line:
                    break
                item = str(line.split()[0], 'utf-8')
                #print(item)
                try:
                    query = 'docker inspect ' + item
                    output = subprocess.check_output(query, shell=True)
                    json_string = json.loads(str(output, 'utf-8'))
                    #print(json_string[0]['Config']['Labels']['io.kubernetes.container.name'])
                    for containerName in self.dockerContainerList:
                        if json_string[0]['Config']['Labels']['com.docker.compose.service']== containerName:
                            print("Find valid container for dockerID:" + item)
                            containerDict[item] = containerName
                            break
                except Exception as newExp:
                    print("Invalid container ID:" + item)

            #finally copy the local dictionary to global one
            self.requiredContainerDict.update(containerDict)
        except Exception as exp:
            print("Error while finding list of the docker container...")

    def getContainerID(self, previousContainerName):
        print("Inside getContainerID...")
        try:
            allContainerList = subprocess.Popen(['docker', 'ps'], stdout=subprocess.PIPE)
            index = 0
            while True:
                line = allContainerList.stdout.readline()
                if not line:
                    break
                item = str(line.split()[0], 'utf-8')

                try:
                    query = 'docker inspect ' + item
                    output = subprocess.check_output(query, shell=True)
                    json_string = json.loads(str(output, 'utf-8'))

                    if json_string[0]['Config']['Labels']['io.kubernetes.container.name']== previousContainerName:
                        return item
                except Exception as newExp:
                    pass
        except Exception as exp:
            print("Error while finding list of the docker container...")

        return ""

    def trimInvalid(self, input):
        for item in invalidCharList:
                input = input.replace(item, '')
        return input

class ContainerMonitoringThread(threading.Thread):

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
        super(ContainerMonitoringThread, self).__init__(group=group, target=target, name=name)
        self.args = args
        self.kwargs = kwargs

    def setName(self, threadName):
        self.threadName = threadName


    def run(self):
        containerID = self.kwargs['containerID']
        containerName = self.kwargs['containerName']
        print('containerID:' + containerID + ", containerName:" + containerName)

        try:
            #create file path and remove previous data
            logFilePath = logFilePathRoot + containerName + ".log"
            pngFilePath = logFilePathRoot + containerName + ".png"
            try:
                os.remove(logFilePath)
            except Exception as exp:
                print("Unable to remove file:" + logFilePath)

            try:
                os.remove(pngFilePath)
            except Exception as exp:
                print("Unable to remove file:" + logFilePath)

            #first write header into the file
            statistics = "datetime,container-id,cpu-usages,memory-usages,memory-limit,memory-percentage,net-input,net-output,block-input,block-output,pid"
            self.file = open(logFilePath, "a")
            self.file.write(statistics + "\n")
            self.file.close()

            #start writing content into the file
            while True:
                global runningThread
                if runningThread == False:
                    print("Request to stop thread for container:" + self.threadName)
                    break
                #docker stats output:
                #
                #CONTAINER ID and Name: The ID and name of the container
                #CPU % and MEM %:       The percentage of the host’s CPU and memory the container is using
                #MEM USAGE / LIMIT:     The total memory the container is using, and the total amount of memory it is allowed to use
                #NET I/O:               The amount of data the container has sent and received over its network interface
                #BLOCK I/O:             The amount of data the container has read to and written from block devices on the host
                #PIDs:                  The number of processes or threads the container has created
                data = ""
                container_crashed = True

                #print("HELLO:" + str(runningThread))
                #while container_crashed or runningThread:
                while container_crashed:
                    try:
                        retString = subprocess.check_output('docker inspect ' + containerID + ' | grep "Running"', shell=True)
                        if str(retString).find('false') != -1:
                            print("Seems container " + containerID + " is crashed, waiting to start with new container...")
                            time.sleep(3)
                            cMonitoring = ContainerMonitoring()
                            newContainerID = cMonitoring.getContainerID(containerName)
                            if newContainerID != "":
                                containerID = newContainerID
                            print("New container is " + containerID + " ...")
                            container_crashed = True
                        else:
                            data = subprocess.check_output('docker stats --no-stream ' + containerID, shell=True, universal_newlines=True)
                            container_crashed = False
                    except:
                        print("Exception while processing the request...")

                processedData = data.split()
                #print(processedData)

                #reset the variable to true
                container_crashed = True

                #datetime
                now = datetime.now()
                statistics = now.strftime("%Y-%m-%d_%H:%M:%S") + ","

                #container id
                statistics = statistics + str(processedData[16]) + ","
                #CPU usages
                statistics = statistics + str(processedData[18]) + ","
                #Memory usages
                statistics = statistics + str(processedData[19]) + ","
                statistics = statistics + str(processedData[21]) + ","
                #Memory percentage
                statistics = statistics + str(processedData[22]) + ","
                #NET I/O
                statistics = statistics + str(processedData[23]) + ","
                statistics = statistics + str(processedData[25]) + ","
                #Block I/O
                statistics = statistics + str(processedData[26]) + ","
                statistics = statistics + str(processedData[28]) + ","
                #PID
                statistics = statistics + str(processedData[29])

                #print(statistics)

                self.file = open(logFilePath, "a")
                self.file.write(statistics + "\n")
                self.file.close()

        except Exception as ex:
            print(ex)

if __name__ == "__main__":
    print("Inside main function")
    cMonitoring = ContainerMonitoring()

    #Setup initial structure
    cMonitoring.setup();

    #Get the the running container from the predefined list
    cMonitoring.getRunningContainer()

    #Span thread to log the statistics of the each container
    threadCounter = 0
    for item in cMonitoring.requiredContainerDict:
        print("Starting thread for container:" + cMonitoring.requiredContainerDict[item])
        thread = ContainerMonitoringThread(args=(threadCounter), kwargs={'containerID':item, 'containerName':cMonitoring.requiredContainerDict[item]})
        thread.setName(cMonitoring.requiredContainerDict[item])
        threadCounter = threadCounter + 1
        thread.start()
        allThread.append(thread)

    time.sleep(1)
    val = input('Enter EXIT/exit, to exit from the program...')

    while True:
        if val == "EXIT" or val == 'exit':
            break

        val = input()
        #wait for while loop for the monitoring
        #time.sleep(1)

    print ("Stopping running threads")
    runningThread = False

    time.sleep(3)

    print('Capturing report and exiting...')
    #while True:
        #wait for while loop for the monitoring
    #    time.sleep(3)

    #signal.signal(signal.SIGINT, signal_handler)
    #print('Press Ctrl+C to exit...')
    #signal.pause()
