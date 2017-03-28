var MAX_ERRORS = 5;  // errors before we just stop
var CHUNK_SIZE = 16384;

// General globals
var baseURL = window.location.href.substring(0, window.location.href.lastIndexOf("/"));
var logElement = null;
var headerElement = null;
var errorCount = 0;
var tasks = null;
var offsets = {};
var lastlog = "";

var tasksToProcess = null;
var currentTaskID = null;
var currentInfo = null;
var currentLogs = null;
var currentLog = null;

function parseTasklist() {
    var tasklist = [];
    var queryStr = unescape(window.location.search.substring(1));
    var vars = queryStr.split('&');
    for (var i=0; i<vars.length; i++) {
        if (vars[i].split('=')[0] == 'taskID') {
            tasklist.push(parseInt(vars[i].split('=')[1]));
        }
    }
    return tasklist;
}

function maybeScroll(origHeight) {
    if ((window.pageYOffset + window.innerHeight) >= origHeight) {
        // Only scroll the window if we were already at the bottom
        // of the document
        window.scroll(window.pageXOffset, document.body.clientHeight);
    }
}

function handleStatus(event) {
    req = event.target;
    if (req.readyState != 4) {
	return;
    }
    if (req.status == 200) {
	if (req.responseText.length > 0) {
	    var lines = req.responseText.split("\n");
	    var line = lines[0];
	    var data = line.split(":");
	    // var taskID = parseInt(data[0]);
	    var state = data[1];
	    var logs = {};
	    for (var i = 1; i < lines.length; i++) {
		data = lines[i].split(":");
		var filename = data[0] + ":" + data[1];
		var filesize = parseInt(data[2]);
		if (filename.indexOf(".log") != -1) {
		    logs[filename] = filesize;
		}
	    }
	} else {
	    // task may not have started yet
	    var state = "UNKNOWN";
	    var logs = {};
	}
	currentInfo = {state: state, logs: logs};
	if (!(state == "FREE" || state == "OPEN" ||
	      state == "ASSIGNED" || state == "UNKNOWN")) {
	    // remove tasks from the task list that are no longer running
	    for (var i = 0; i < tasks.length; i++) {
		if (tasks[i] == currentTaskID) {
		    tasks.splice(i, 1);
		    break;
		}
	    }
	}
    } else {
	currentInfo = {state: "UNKNOWN", logs: {}};
	popupError("Error checking status of task " + currentTaskID + ": " + req.statusText);
    }
    currentLogs = [];
    for (var logname in currentInfo.logs) {
	currentLogs.push(logname);
    }
    processLog();
}

function getStatus() {
    if (tasksToProcess.length == 0) {
	if (errorCount > MAX_ERRORS) {
	    return;
	} else {
	    if (headerElement != null) {
		headerElement.appendChild(document.createTextNode("."));
	    }
	    setTimeout(checkTasks, 5000);
	    return;
	}
    }

    currentTaskID = tasksToProcess.shift();
    var req = new XMLHttpRequest();
    req.open("GET", baseURL + "/taskstatus?taskID=" + currentTaskID, true);
    req.onreadystatechange = handleStatus;
    req.send(null);
}

function checkTasks() {
    if (tasks.length == 0) {
	docHeight = document.body.clientHeight;
        logElement.appendChild(document.createTextNode("\n==> Task has completed <==\n"));
        maybeScroll(docHeight);
    } else {
	tasksToProcess = [];
	for (var i = 0; i < tasks.length; i++) {
	    tasksToProcess.push(tasks[i]);
	}
	getStatus();
    }
}

function processLog() {
    if (currentLogs.length == 0) {
	getStatus();
	return;
    }
    currentLog = currentLogs.shift();
    var taskOffsets = offsets[currentTaskID];
    if (!(currentLog in taskOffsets)) {
	taskOffsets[currentLog] = 0;
    }
    outputLog();
}

function outputLog() {
    var currentOffset = offsets[currentTaskID][currentLog];
    var currentSize = currentInfo.logs[currentLog];
    if (currentSize > currentOffset) {
	var chunkSize = CHUNK_SIZE;
	if ((currentSize - currentOffset) < chunkSize) {
	    chunkSize = currentSize - currentOffset;
	}
	var req = new XMLHttpRequest();
	var data = currentLog.split(':');
	var volume = data[0];
	var filename = data[1];
	req.open("GET", baseURL + "/getfile?taskID=" + currentTaskID + "&name=" + filename +
                 "&volume=" + volume + "&offset=" + currentOffset + "&size=" + chunkSize, true);
	req.onreadystatechange = handleLog;
	req.send(null);
	if (headerElement != null) {
	    logElement.removeChild(headerElement);
	    headerElement = null;
	}
    } else {
	processLog();
    }
}

function handleLog(event) {
    req = event.target;
    if (req.readyState != 4) {
	return;
    }
    if (req.status == 200) {
	content = req.responseText;
	offsets[currentTaskID][currentLog] += content.length;
	if (content.length > 0) {
	    docHeight = document.body.clientHeight;
	    currlog = currentTaskID + ":" + currentLog;
	    if (currlog != lastlog) {
		logElement.appendChild(document.createTextNode("\n==> " + currlog + " <==\n"));
		lastlog = currlog;
	    }
	    logElement.appendChild(document.createTextNode(content));
	    maybeScroll(docHeight);
	}
    } else {
	popupError("Error retrieving " + currentLog + " for task " + currentTaskID + ": " + req.statusText);
    }
    outputLog();
}

function popupError(msg) {
    errorCount++;
    alert(msg);
}

function watchLogs(element) {
    logElement = document.getElementById(element);
    headerElement = logElement.firstChild;
    tasks = parseTasklist();
    for (var i=0; i<tasks.length; i++) {
        offsets[tasks[i]] = {};
    }

    setTimeout(checkTasks, 1000);
}
