###############################################################################
#                                                                             #
# Copyright 2015.  Los Alamos National Security, LLC. This material was       #
# produced under U.S. Government contract DE-AC52-06NA25396 for Los Alamos    #
# National Laboratory (LANL), which is operated by Los Alamos National        #
# Security, LLC for the U.S. Department of Energy. The U.S. Government has    #
# rights to use, reproduce, and distribute this software.  NEITHER THE        #
# GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES ANY WARRANTY,        #
# EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  #
# If software is modified to produce derivative works, such modified software #
# should be clearly marked, so as not to confuse it with the version          #
# available from LANL.                                                        #
#                                                                             #
# Additionally, this program is free software; you can redistribute it and/or #
# modify it under the terms of the GNU General Public License as published by #
# the Free Software Foundation; either version 2 of the License, or (at your  #
# option) any later version. Accordingly, this program is distributed in the  #
# hope that it will be useful, but WITHOUT ANY WARRANTY; without even the     #
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    #
# See the GNU General Public License for more details.                        #
#                                                                             #
###############################################################################
'''
Created on Feb 13, 2013

The ReduceSudoTimeout class removes the default 5 minute window of stored sudo
authorization after a successful sudo authorization is made.

@author: bemalmbe
@change: 02/14/2014 ekkehard Implemented self.detailedresults flow
@change: 02/14/2014 ekkehard Implemented isapplicable
@change: 03/27/2014 ekkehard make os x mavericks compliant
@change: 04/18/2014 dkennel Replaced mid-style CI invocation.
@change: 05/07/2014 dwalker testing and refactoring rule
@change: 2015/04/16 dkennel updated for new isApplicable
'''
from __future__ import absolute_import
import re
import os
import datetime
import traceback

from ..rule import Rule
from ..stonixutilityfunctions import checkPerms, iterate
from ..stonixutilityfunctions import setPerms, readFile, writeFile, resetsecon
from ..logdispatcher import LogPriority


class ReduceSudoTimeout(Rule):
    '''
    The ReduceSudoTimeout class removes the default 5 minute window of stored
    sudo authorization after a successful sudo authorization is made.
    @author bemalmbe
    '''

    def __init__(self, config, environ, logdispatch, statechglogger):
        '''
        Constructor
        '''

        Rule.__init__(self, config, environ, logdispatch, statechglogger)

        self.logger = logdispatch
        self.rulenumber = 151
        self.rulename = 'ReduceSudoTimeout'
        self.formatDetailedResults("initialize")
        self.helptext = "ReduceSudoTimeout ensures that the sudoers file " + \
        "has a timeout value of 0 so that a password is required for " + \
        "every sudo call.  This is mandatory for Mac users but optional " + \
        "for all other platforms. ***Please note, for all systems besides " + \
        "Mac OS X, this rule is disabled by default.  To enable, click " + \
        "the enable box then click save before running fix****"
        self.guidance = ['N/A']
        self.applicable = {'type': 'white',
                           'family': ['linux', 'solaris', 'freebsd'],
                           'os': {'Mac OS X': ['10.9', 'r', '10.10.10']}}
        datatype = 'bool'
        key = 'ReduceSudoTimeout'
        instructions = "If set to yes or true the REDUCESUDOTIMEOUT " + \
        "variable will set the sudo timeout to 0 requiring a password " + \
        "for each command."
        if self.environ.getostype() == 'Mac OS X':
            self.mandatory = True
            default = True
        else:
            default = False
        self.ci = self.initCi(datatype, key, instructions, default)
        self.iditerator = 0

###############################################################################

    def report(self):
        '''
        determine whether 5 minute window of stored sudo credentials is
        disabled. self.compliant, self.detailed results and self.currstate
        properties are updated to reflect the system status. self.rulesuccess
        will be updated if the rule does not succeed.

        @return bool
        @author bemalmbe
        '''

        # defaults
        try:
            self.detailedresults = ""
            compliant = True
            if self.environ.getostype() == "Mac OS X":
                sudo = "/private/etc/sudoers"
            else:
                sudo = "/etc/sudoers"
            if os.path.exists(sudo):
                if not checkPerms(sudo, [0, 0, 288], self.logger):
                    compliant = False
                contents = readFile(sudo, self.logger)
                if contents:
                    found = False
                    for line in contents:
                        if re.search("^Defaults\s+timestamp_timeout", line.strip()):
                            found = True
                            if re.search("=", line.strip()):
                                temp = line.split("=")
                                try:
                                    if temp[1].strip() != "0":
                                        compliant = False
                                except IndexError:
                                    debug = traceback.format_exc() + "\n"
                                    debug += "Index out of range on line: " + line + "\n"
                                    self.logger.log(LogPriority.DEBUG, debug)
                    if not found:
                        compliant = False
            if compliant:
                self.compliant = True
                self.detailedresults = "ReuduceSudoTimeout report has been \
run and is compliant\n"
            else:
                self.compliant = False
                self.detailedresults = "ReuduceSudoTimeout report has been \
run and is not compliant\n"
        except (KeyboardInterrupt, SystemExit):
            # User initiated exit
            raise
        except Exception:
            self.rulesuccess = False
            self.complaint = False
            self.detailedresults += "\n" + traceback.format_exc()
            self.logdispatch.log(LogPriority.ERROR, self.detailedresults)
        self.formatDetailedResults("report", self.compliant,
                                   self.detailedresults)
        self.logdispatch.log(LogPriority.INFO, self.detailedresults)
        return self.compliant
    
###############################################################################

    def fix(self):
        '''
        set the sudo timeout to 0. self.rulesuccess will be updated if this
        method does not succeed.  In this rule in particular, we will not 
        attempt to install or create a sudo file if not already present

        @author bemalmbe
        '''

        try:
            if not self.ci.getcurrvalue():
                return
            
            #clear out event history so only the latest fix is recorded
            self.iditerator = 0
            eventlist = self.statechglogger.findrulechanges(self.rulenumber)
            for event in eventlist:
                self.statechglogger.deleteentry(event)
                
            self.detailedresults = ""
            if self.environ.getostype() == "Mac OS X":
                sudo = "/private/etc/sudoers"
            else:
                sudo = "/etc/sudoers"
            tsudo = sudo + ".tmp"
            success = True
            badfile = False
            tempstring = ""
            if os.path.exists(sudo):
                if not checkPerms(sudo, [0, 0, 288], self.logger):
                    self.iditerator += 1
                    myid = iterate(self.iditerator, self.rulenumber)
                    if setPerms(sudo, [0, 0, 288], self.logger,
                                                    self.statechglogger, myid):
                        self.detailedresults += "successfully corrected \
permissions on file: " + sudo + "\n"
                    else:
                        success = False
                        self.detaileresults += "Was not able to successfully \
set permissions on file: " + sudo + "\n"
                contents = readFile(sudo, self.logger)
                if contents:
                    found = False
                    for line in contents:
                        if re.search("^Defaults\s+timestamp_timeout", line.strip()):
                            if re.search("=", line.strip()):
                                temp = line.split("=")
                                try:
                                    if temp[1].strip() == "0":
                                        found = True
                                        tempstring += line
                                    else:
                                        badfile = True
                                except IndexError:
                                    badfile = True
                                    debug = traceback.format_exc() + "\n"
                                    debug += "Index out of range on line: " + line + "\n"
                                    self.logger.log(LogPriority.DEBUG, debug)
                            else:
                                badfile = True
                        else:
                            tempstring += line
                    if not found:
                        badfile = True
                        tempstring += "Defaults      timestamp_timeout=0\n"
                if badfile:
                    if writeFile(tsudo, tempstring, self.logger):
                        self.iditerator += 1
                        myid = iterate(self.iditerator, self.rulenumber)
                        event = {"eventtype":"conf",
                                 "filepath":sudo}
                        self.statechglogger.recordchgevent(myid, event)
                        self.statechglogger.recordfilechange(sudo, tsudo, myid)
                        self.detailedresults += "corrected sudo timeout \
contents of " + sudo + "\n"
                        os.rename(tsudo, sudo)
                        os.chown(sudo, 0 , 0)
                        os.chmod(sudo, 288)
                        resetsecon(sudo)
                    else:
                        self.detailedresults += "Unable to successfully write \
the file: " + sudo + "\n"
                        success = False
            self.rulesuccess = success
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.rulesuccess = False
            self.detailedresults += "\n" + traceback.format_exc()
            self.logdispatch.log(LogPriority.ERROR, self.detailedresults)
        self.formatDetailedResults("fix", self.rulesuccess,
                                   self.detailedresults)
        self.logdispatch.log(LogPriority.INFO, self.detailedresults)
        return self.rulesuccess