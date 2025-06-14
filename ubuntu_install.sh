#!/usr/bin/env bash
set -e

apt-get update
apt-get install --yes \
  build-essential cmake pkg-config libssl-dev libzmq3-dev \
  libunbound-dev libsodium-dev libunwind-dev liblzma-dev \
  libminiupnpc-dev libpcsclite-dev libreadline-dev libldns-dev \
  libexpat1-dev libpgm-dev qttools5-dev-tools libhidapi-dev \
  libusb-1.0-0-dev libprotobuf-dev protobuf-compiler libudev-dev \
  libboost-chrono-dev libboost-date-time-dev libboost-filesystem-dev \
  libboost-locale-dev libboost-program-options-dev libboost-regex-dev \
  libboost-serialization-dev libboost-system-dev libboost-thread-dev \
  libgtest-dev ccache doxygen graphviz

git submodule update --init --recursive

echo "Dependencies and submodules ready"

