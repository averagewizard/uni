#-*- coding: utf8 -*-

# Copyright (C) 2013  Eren Türkay <turkay.eren@gmail.com>

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

######## NOTE! ##########
# This is a modified and stripped down version of irc server. Since the
# previous version was highly extensible, I added "broadcast" command and
# only relay pixel information to other clients.

# Although there are functions for nicks, I don't use nicks in the clients
######## NOTE! ##########

import socket
import threading
import os
import sys

class CommandHandler(object):
    """
    Handle the command from the user

    This class is initialized after the thread is created to handle the
    connection and the received line is parsed for command and arguments.

    The class has one-to-one relationship with each command and
    functions. If the command has corresponding callable method within
    this class, it is called. If not, the error is sent to the client.
    """
    def __init__(self, connection, chatservice):
        """
        It gets the client's socket connection and the shared data structure
        across the threads to hold nickname, connection descriptor, etc.

        ChatService is probably the most important one because it holds
        the dictionary structure about connections.
        """

        self.connection = connection
        self.chatservice = chatservice

        # Since we directly call the command if it's callable, a user
        # might send 'run', 'get_own_nick' commands to call internal
        # functions. For this not to happen, we need to filter such
        # commands, and do not call them
        self.exclude_commands = ['run', '__send_broadcast', 'send']

    ############################################################
    #                                                          #
    # Internal functions                                       #
    #                                                          #
    ############################################################
    def __send_broadcast(self, data):
        descriptors = self.chatservice.get_descriptors()

        for i in descriptors:
            conn = descriptors[i]['conn']
            conn.send('%s\n' % data)

    def run(self, command, args=[]):
        # Exclude the commands for misuse
        if (command in self.exclude_commands):
            pass

        if (hasattr(self, command)):
            command_to_run = getattr(self, command)
            command_to_run(args)
        else:
             self.send('ERROR: Unknown command "%s"' % command)

    def send(self, data):
        self.connection.send('%s\n' % data)

    ############################################################
    #                                                          #
    # Chat Commands                                            #
    #                                                          #
    ############################################################
    def broadcast(self, msg):
        """
        Send everyone a message.

        Syntax:
            broadcast: <message>
        """
        self.__send_broadcast(msg)

    def quit(self, arg):
        """
        Quit from the chat.

        Syntax:
            quit:
        """
        desc = self.chatservice.get_descriptor(self.connection.fileno())

        if (desc and desc.has_key('nick')):
            nick = desc['nick']
        else:
            nick = self.connection.fileno()

        self.__send_broadcast('<broadcast: SYSTEM>: %s has left the \
chat' % nick)
        self.chatservice.remove_descriptor(self.connection)
        self.send('Bye!')
        self.connection.close()
        sys.exit(1)

class ChatService(object):
    """
    Chat service that handles connections, nicknames, shared structures,
    etc.

    This class is initialized before we accept the client connections so
    that the threads can share data structures.  When the client is
    connected and it is accepted, a seperate thread is created and
    "handle_connection()" method is called.
    
    This method, then, adds the client information into shared data
    structure, parses the data (commands, arguments) received from the
    client, initializes CommandHandler() and runs it for processing the
    command
    """

    def __init__(self):
        """
        Shared dictionary across threads to hold connection
        information as well as the client's nicknames

        This structure of the dictionary is as follows:
            descriptors:
            {file-descriptor-number} = {
                'conn': client's socket
                'nick': client's nickanme
                }
            }

            nick:
            {'nickname': client's socket}

        """
                                        
        self.__descriptors = {}
        self.__nicks = {}

    def broadcast(self):
        descriptors = self.__descriptors

        for i in descriptors:
            conn = descriptors[i]['conn']
            conn.send('%s\n' % data)

    def get_descriptors(self):
        return self.__descriptors

    def get_descriptor(self, fd):
        if (self.__descriptors.has_key(fd)):
            return self.__descriptors[fd]

        return False

    def get_nicks(self):
        return self.__nicks

    def get_nick(self, nick):
        if (self.__nicks.has_key(nick)):
            return self.__nicks[nick]

        return False

    def set_descriptor(self, fd, data_dict):
        self.__descriptors[fd].update(data_dict)

    def set_nick(self, nick, connection):
        self.__nicks[nick] = connection

    def add_descriptor(self, connection):
        """
        Add the connection to descriptor map. This method is called when
        the client connection is established.
        """
        self.__descriptors[connection.fileno()] = {'conn': connection}

    def remove_descriptor(self, connection):
        """
        Remove the connection from descriptor map. It is removed when
        the connection is ended in client side or when a socket error
        occured.
        """
        fd = connection.fileno()

        if (self.__descriptors[fd].has_key('nick')):
            del self.__nicks[self.__descriptors[fd]['nick']]

        del self.__descriptors[fd]

    def debug(self, data):
        print 'DEBUG: %s' % data

    def parse_command(self, line, connection):
        """
        Parse the command and handle it to CommandHandler
        """
        if (len(line) <= 1):
            self.debug('Empty line received.')
            connection.send('\n')
        else:
            split = line.split(':')
            if (len(split) <= 1):
                connection.send('ERROR: Cannot parse command. Please \
write the command in "COMMAND: argument1 argument2" form\n')
            else:
                # Replace the newlines and any blank lines in the
                # beginning of the mssage. Since we have one-to-one
                # relationship between commands and CommandHandler
                # methods, we need to replace - with _ in the command.
                # Python does not allow - in methods
                command = split[0].replace('-', '_').replace('\n', '') \
                        .strip()
                argument = split[1].replace('\n', '').strip()

                command_handler = CommandHandler(connection, self)
                command_handler.run(command, argument)

    def handle_connection(self, connection):
        """ 
        This method works like __init__. It initializes required
        variables such as connection when the connection is made and new
        thread is created.
        """
        try:
            current_thread = threading.current_thread()

            # add connection information, from which thread it is
            # handled to descriptor list
            self.add_descriptor(connection)

            self.debug('Connection Made: %s' % connection.fileno())
            self.debug(self.__descriptors)

            while True:
                line = connection.recv(1024)
                self.parse_command(line, connection)

        except IOError as e:
            thread_name = current_thread.getName()

            self.remove_descriptor(connection)

            self.debug('[%s] Error! "%s"' % (thread_name, e))
            self.debug('[%s] Exiting...' % thread_name)
            sys.exit(1)

def __control_arguments():
    if (len(sys.argv) <= 1):
        print 'ERROR: Please provide a port to bind'
        sys.exit(1)

def main():
    __control_arguments()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', int(sys.argv[1])))

    server.listen(10)
    print '[+] Server started on port %s' % sys.argv[1]

    chatService = ChatService()
    try:
        while True:
            clientConnection, clientAddr = server.accept()

            t = threading.Thread(target=chatService.handle_connection, \
                    args=[clientConnection])
            t.setDaemon(True)
            t.start()
    except KeyboardInterrupt:
        print '[-] KeyboardInterrupt. Exiting...'
        server.close()
        sys.exit(0)

if __name__ == '__main__':
    main()

