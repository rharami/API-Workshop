FROM ubuntu
MAINTAINER RyanHarami rharami@gmail.com
RUN apt-get update
RUN DEBIAN_FRONTEND='noninteractive' apt-get install -y \
	build-essential \
	software-properties-common \
	python3-pip \
	nano

RUN pip3 install meraki
RUN pip3 install influxdb-client
RUN pip3 install jsonpickle

RUN mkdir meraki
RUN cd meraki

ADD influx.py /meraki

