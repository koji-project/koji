/*
  Copyright (c) 2005 Jan-Klaas Kollhof
  
  This file is part of the JavaScript o lait library(jsolait).
  
  jsolait is free software; you can redistribute it and/or modify
  it under the terms of the GNU Lesser General Public License as published by
  the Free Software Foundation; either version 2.1 of the License, or
  (at your option) any later version.
 
  This software is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Lesser General Public License for more details.
 
  You should have received a copy of the GNU Lesser General Public License
  along with this software; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/

        
/**
    Provides a lightweight JSON-RPC imlementation for JSON-RPC over HTTP.
    @creator Jan-Klaas Kollhof
    @created 2005-02-25
*/
Module("jsonrpc","0.4.2", function(mod){
    var urllib = importModule("urllib");
    /**
        Thrown if a  server did not respond with response status 200 (OK).
    */
    mod.InvalidServerResponse = Class(mod.Exception, function(publ, supr){
        /**
            Initializes the Exception.
            @param status       The status returned by the server.
        */
        publ.init= function(status){
            supr(this).init("The server did not respond with a status 200 (OK) but with: " + status);
            this.status = status;
        }
         ///The status returned by the server.
        publ.status;
    })
    
    /**
        Thrown if an JSON-RPC response is not well formed.
    */
    mod.MalformedJSONRpc = Class(mod.Exception, function(publ, supr){
        /**
            Initializes the Exception.
            @param msg          The error message of the user.
            @param json           The json source.
            @param trace=null  The error causing this Exception
        */
        publ.init= function(msg, s, trace){
            supr(this).init(msg,trace);
            this.source = s;
        }
         ///The json source which was mal formed.
        publ.source;
    })
    /**
        Thrown if an JSON-RPC error is returned.
    */
    mod.JSONRPCError = Class(mod.Exception, function(publ, supr){
        /**
            Initializes the Exception.
            @param err          The error object.
            @param trace=null  The error causing this Exception
        */
        publ.init= function(err, trace){
            supr(this).init(err,trace);
        }
    })
    
    
    /**
        Marshalls an object to JSON.(Converts an object into JSON conforming source.)
        It just calls the toJSON function of the objcect.
        So, to customize serialization of objects one just needs to specify/override the toXmlRpc method 
        which should return an xml string conforming with XML-RPC spec.
        @param obj    The object to marshall
        @return         An xml representation of the object.
    */
    mod.marshall = function(obj){
        if(obj == null){
            return "null";
        }else if(obj.toJSON){
            return obj.toJSON();
        }else{
            var v=[];
            for(var attr in obj){
                if(typeof obj[attr] != "function"){
                    v.push('"' + attr + '": ' + mod.marshall(obj[attr]));
                }
            }
            return "{" + v.join(", ") + "}";
        }
    }
    
    /**
        Unmarshalls a JSON source to a JavaScript object. 
        @param source    The source  to unmarshall.
        @return         The JavaScript object created.
    */
    mod.unmarshall = function(source){
        try {
            var obj;
            eval("obj=" + source);
            return obj;
        }catch(e){
            throw new mod.MalformedJSONRpc("The server's response could not be parsed.", source, e);
        }
    }
    /**
        Class for creating JSON-RPC methods.
        Calling the created method will result in a JSON-RPC call to the service.
        The return value of this call will be the return value of the RPC call.
        RPC-Errors will be raised as Exceptions.
        
        Asynchronous operation:
        If the last parameter passed to the method is an JSONRPCAsyncCallback object, 
        then the remote method will be called asynchronously. 
        The results and errors are passed to the callback.
    */
    mod.JSONRPCMethod =Class(function(publ){
        
        var postData = function(url, user, pass, data, callback){
            if(callback == null){
                var rslt = urllib.postURL(url, user, pass, data, [["Content-Type", "text/plain"]]);
                return rslt;
            }else{
                urllib.postURL(url, user, pass, data, [["Content-Type", "text/xml"]], callback);
            }
        }
        
        var handleResponse=function(resp){
            var status=null;
            try{//see if the server responded with a response code 200 OK.
                status = resp.status;
            }catch(e){
            }
            if(status == 200){
                var respTxt = ""; 
                try{                 
                    respTxt=resp.responseText;
                }catch(e){
                }
                if(respTxt == null || respTxt == ""){
                    throw new mod.MalformedJSONRpc("The server responded with an empty document.", "");
                }else{
                    var rslt = mod.unmarshall(respTxt);
                    if(rslt.error != null){
                        throw new mod.JSONRPCError(rslt.error);
                    }else{
                        return rslt.result;
                    }
                }
            }else{
                throw new mod.InvalidServerResponse(status);
            }
        }
        
        var jsonRequest = function(id, methodName, args){
            var p = [mod.marshall(id), mod.marshall(methodName), mod.marshall(args)];
            return '{"id":' + p[0] + ', "method":' + p[1] + ', "params":' + p[2] + "}";
        }
        /**
            Initializes the JSON-RPC method.
            @param url                 The URL of the service providing the method.
            @param methodName   The name of the method to invoke.
            @param user=null             The user name to use for HTTP authentication.
            @param pass=null             The password to use for HTTP authentication.
        */
        publ.init = function(url, methodName, user, pass){
            
            //this is pretty much a hack.
            //we create a function which mimics this class and 
            //return it instead of realy instanciating an object. 
            var fn=function(){
                var args=new Array();
                for(var i=0;i<arguments.length;i++){
                    args.push(arguments[i]);
                }
                //sync or async call
                if(typeof arguments[arguments.length-1] != "function"){
                    var data=jsonRequest("httpReq", fn.methodName, args);
                    var resp = postData(fn.url, fn.user, fn.password, data);
                    return handleResponse(resp);
                }else{
                    var cb = args.pop(); //get rid of the function argument
                    var data=jsonRequest("httpReq", fn.methodName, args);
                    postData(fn.url, fn.user, fn.password, data, function(resp){
                        var rslt = null;
                        var exc =null;
                        try{
                            rslt = handleResponse(resp);
                        }catch(e){
                            exc = e;
                        }
                        try{//call the callback for the async call.
                            cb(rslt,exc);
                        }catch(e){
                        }
                        args = null;
                        resp = null;
                    });
                }
            }
            //make sure the function has the same property as an object created from this class.
            fn.methodName = methodName;
            fn.notify = this.notify;
            fn.url = url;
            fn.user = user;
            fn.password=pass;
            fn.toString = this.toString;
            fn.setAuthentication=this.setAuthentication;
            fn.constructor = this.constructor;
            
            return fn;
        }
                
        /**
            Sets username and password for HTTP Authentication.
            @param user    The user name.
            @param pass    The password.
        */
        publ.setAuthentication = function(user, pass){
            this.user = user;
            this.password = pass;
        }
        
        /** 
            Sends the call as a notification which does not have a response.
            Call this as if you would call the method itself. Callbacks are ignored.
        */
        publ.notify = function(){
            var args=new Array();
            for(var i=0;i<arguments.length;i++){
                args.push(arguments[i]);
            }
            var data=jsonRequest(null, this.methodName, args);
            postData(this.url, this.user, this.password, data, function(resp){});
        }
        
        ///The name of the remote method.
        publ.methodName;
        ///The url of the remote service containing the method.
        publ.url;
        ///The user name used for HTTP authorization.
        publ.user;
        ///The password used for HTTP authorization.
        publ.password;
    })
    
    /**
        Creates proxy objects which resemble the remote service.
        Method calls of this proxy will result in calls to the service.
    */
    mod.ServiceProxy=Class("ServiceProxy", function(publ){
        /**
            Initializes a new ServerProxy.
            The arguments are interpreted as shown in the examples:
            ServerProxy("url", ["methodName1",...])
            ServerProxy("url", ["methodName1",...], "user", "pass")
            ServerProxy("url", "user", "pass")
            
            @param url                     The url of the service.
            @param methodNames      Array of names of methods that can be called on the server.
            @param user=null             The user name to use for HTTP authentication.
            @param pass=null             The password to use for HTTP authentication.
        */
        publ.init = function(url, methodNames, user, pass){
            this._url = url;
            this._user = user;
            this._password = pass;
            this._addMethodNames(methodNames);
        }
        
        /**
            Adds new JSONRPCMethods to the proxy server which can then be invoked.
            @param methodNames   Array of names of methods that can be called on the server.
        */
        publ._addMethodNames = function(methodNames){
            for(var i=0;i<methodNames.length;i++){
                var obj = this;
                //setup obj.childobj...method
                var names = methodNames[i].split(".");
                for(var n=0;n<names.length-1;n++){
                    var name = names[n];
                    if(obj[name]){
                        obj = obj[name];
                    }else{
                        obj[name]  = new Object();
                        obj = obj[name];
                    }
                }
                var name = names[names.length-1];
                if(obj[name]){
                }else{
                    var mth = new mod.JSONRPCMethod(this._url, methodNames[i], this._user, this._password);
                    obj[name] = mth;
                    this._methods.push(mth);
                }
            }
        }
        
        /**
            Sets username and password for HTTP Authentication for all methods of this service.
            @param user    The user name.
            @param pass    The password.
        */
        publ._setAuthentication = function(user, pass){
            this._user = user;
            this._password = pass;
            for(var i=0;i<this._methods.length;i++){
                this._methods[i].setAuthentication(user, pass);
            }
        }
        
        ///The url of the service to resemble.
        publ._url;
        ///The user used for HTTP authentication.
        publ._user;
        ///The password used for HTTP authentication.
        publ._password;
        ///All methods.
        publ._methods=new Array();
    })
    
    ///@deprecated  Use ServiceProxy instead.
    mod.ServerProxy= mod.ServiceProxy;
    
    /**
        Converts a String to JSON.
    */
    String.prototype.toJSON = function(){
        var s = '"' + this.replace(/(["\\])/g, '\\$1') + '"';
        s = s.replace(/(\n)/g,"\\n");
        return s;
    }
    
    /**
        Converts a Number to JSON.
    */
    Number.prototype.toJSON = function(){
        return this.toString();
    }
    
    /**
        Converts a Boolean to JSON.
    */
    Boolean.prototype.toJSON = function(){
        return this.toString();
    }
    
    /**
        Converts a Date to JSON.
        Date representation is not defined in JSON.
    */
    Date.prototype.toJSON= function(){
        var padd=function(s, p){
            s=p+s
            return s.substring(s.length - p.length)
        }
        var y = padd(this.getUTCFullYear(), "0000");
        var m = padd(this.getUTCMonth() + 1, "00");
        var d = padd(this.getUTCDate(), "00");
        var h = padd(this.getUTCHours(), "00");
        var min = padd(this.getUTCMinutes(), "00");
        var s = padd(this.getUTCSeconds(), "00");
        
        var isodate = y +  m  + d + "T" + h +  ":" + min + ":" + s;
        
        return '{"jsonclass":["sys.ISODate", ["' + isodate + '"]]}';
    }
    
    /**
        Converts an Array to JSON.
    */
    Array.prototype.toJSON = function(){
        var v = [];
        for(var i=0;i<this.length;i++){
            v.push(mod.marshall(this[i])) ;
        }
        return "[" + v.join(", ") + "]";
    }

    mod.test = function(){
        try{
            print("creating ServiceProxy object using introspection for method construction...\n");
            var s = new mod.ServiceProxy("http://localhost/testj.py",["echo"]);
            print("%s created\n".format(s));
            print("creating and marshalling test data:\n");
            var o = [1.234, 5, {a:"Hello ' \" World", b:new Date()}];
            print(mod.marshall(o));
            print("\ncalling echo() on remote service...\n");
            var r = s.echo(o);
            print("service returned data(marshalled again):\n")
            print(mod.marshall(r));
        }catch(e){
            reportException(e);
        }
    }
})


