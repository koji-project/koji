// Direct jsolait to its install location
jsolait.libURL ="/koji-static/js/jsolait";

// import modules
var codecs = importModule("codecs");
var xmlrpc = importModule("xmlrpc");

// Config variables
var SERVER_URL = 'http://' + window.location.hostname + '/kojihub';
var ELEM_ID = 'logs';  // id of the html element where the logs will be
var MAX_ERRS = 5;  // errors before we just stop
// if you are testing this script from somewhere that isn't SERVER_URL
// set TESTING true
var TESTING = false;

// General globals
var server = null;
var errCount = 0;

// Globals for watch_logs_rec
var offsets = {};
var lastlog = "";

function parse_tasklist() {
    var tasklist = [];
    var queryStr = unescape(window.location.search.substring(1));
    var vars = queryStr.split('&');
    for (var i=0; i<vars.length; i++) {
        if (vars[i].split('=')[0] == 'taskID') {
            tasklist.push(parseInt(vars[i].split('=')[1],10));
        }
    }
    return tasklist;
}

function connect() {
    try {
        server = new xmlrpc.ServerProxy(SERVER_URL, ['downloadTaskOutput', 'taskFinished', 'listTaskOutput']);
    } catch(e) {
        popup_error(e, "Error setting up server connection:");
        errCount++;
    }
}

function maybeScroll(origHeight) {
    if ((window.pageYOffset + window.innerHeight) >= origHeight) {
        // Only scroll the window if we were already at the bottom
        // of the document
        window.scroll(window.pageXOffset, document.height);
    }
}

function watch_logs(tasklist) {
    for (var i=0; i<tasklist.length; i++) {
        offsets[tasklist[i]] = {};
    }

    setTimeout(watch_logs_rec, 1000, tasklist);
}

function watch_logs_rec(tasklist) {
    var logElem = document.getElementById(ELEM_ID);
    var is_finished = false;
    var task_id = -1;
    var output = null;
    var taskoffsets = null;
    var data = "";
    var content = "";
    var log = "";
    var currlog = "";
    var docHeight = 0;

    try {
        if (TESTING) {netscape.security.PrivilegeManager.enablePrivilege("UniversalBrowserRead");}
    } catch (e) {
        popup_error(e, "Error getting browser permissions, watching logs may fail: ");
    }

    for (var i=0; i<tasklist.length; i++) {
        task_id = tasklist[i]; 
        
        try {
            if (server.taskFinished(task_id)) {
                tasklist.splice(i,1); // remove tasklist[i] from tasklist
            }
        } catch (e) {
            popup_error(e, "Error checking if task was finished:");
            errCount++;
            continue;
        }

        try {
            output = server.listTaskOutput(task_id);
        } catch (e) {
            popup_error(e, "Error getting a list of outputed files for task:");
            errCount++;
            continue;
        }

        taskoffsets = offsets[task_id];

        for (var j=0; j<output.length; j++) {
            log = output[j];
            if (log.slice(-4).toLowerCase() == ".log") {
                if (!(log in taskoffsets)) {
                  taskoffsets[log] = 0;
                }

		do {
		    try {
			data = server.downloadTaskOutput(task_id, log, taskoffsets[log], 16384);
		    } catch(e) {
			popup_error(e, "Error while fetching log for task:");
			errCount++;
			continue;
		    }
		    
		    data = data.replace(/\n/gi, '');
		    content = data.decode("base64");
		    taskoffsets[log] += content.length;
		    
		    if (content.length > 0) {
			docHeight = document.height;
			currlog = task_id + ":" + log;
			if (currlog != lastlog) {
			    logElem.appendChild(document.createTextNode("\n==> " + currlog + " <==\n"));
			    lastlog = currlog;
			}                    
			logElem.appendChild(document.createTextNode(content));
                        maybeScroll(docHeight);
                    }
                } while (content.length > 0);
            }
        }
    }

    if (tasklist.length == 0) {
        docHeight = document.height;
        logElem.appendChild(document.createTextNode("\n==> Tasks have finished <==\n"));
        maybeScroll(docHeight);
    } else if (errCount < MAX_ERRS) {
        setTimeout(watch_logs_rec, 1000, tasklist);
    }
}

function popup_error(e, msg) {
    var err;
    if (e.toTraceString) {
        err = e.toTraceString();
    } else {
        err = e.message;
    }
    alert(msg + "\n" + err);
}

function main() {
    var tasklist = parse_tasklist();
    connect();
    try {
        watch_logs(tasklist);
    } catch(e) {
        popup_error(e, "Error while watching logs:");
        errCount++;
    }
}
