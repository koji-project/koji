/*
  Copyright (c) 2004 Jan-Klaas Kollhof
 
  This is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.
 
  This software is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
 
  You should have received a copy of the GNU General Public License
  along with this software; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 
*/

/**
    Iterator module providing iteration services.
    There are two main functions forin and fora for iterating over iteratable objects.
    An iteratable object is an object which has an iterator function which returns an Iterator object.
    forin iterates over the object synchronously calling a callback for each item.
    fora does the same but in an asynchronous matter.
    The Range class is there to create an iteratable object over a range of numbers.
    @creator Jan-Klaas Kollhof
    @created 2004-12-08
*/
Module("iter", "0.0.2", function(mod){
    /**
        Raised if there are no more items an iterator can return.
    */
    mod.StopIteration=Class(mod.Exception, function(publ, supr){
        publ.init=function(){
            supr(this).init("No more Items");
        }
    })
    
    /**
        Base class for Iterators.
    */
    mod.Iterator=Class(function(publ, supr){
        publ.init=function(){
        }
        /**
            Returns the next item in the iteration.
            If there is no item left it throws StopIteration
        */
        publ.next=function(){
            throw new mod.StopIteration();
        }
        /**
            Used so an Iterator can be passed to iteration functions.
        */
        publ.iterator = function(){
            return this;
        }
        
    })
    
    /**
        A simple range class to iterate over a range of numbers.
    */
    mod.Range =Class(mod.Iterator, function(publ, supr){
        /**
            Initializes a new range.
            @param start=0  The first item in the range.
            @param end  The last item in the range.
            @param step The steps between each Item.
        */
        publ.init=function(start, end, step){
            this.current = null;
            switch(arguments.length){
                case 1:
                    this.start = 0;
                    this.end = start;
                    this.step = 1;
                    break;
                case 2:
                    this.start = start;
                    this.end = end;
                    this.step =1;
                    break;
                case 3:
                    this.start = start;
                    this.end = end;
                    this.step = step;
                    break;
            }
            this.current=this.start - this.step;
        }
        
        publ.next = function(){
            if(this.current + this.step > this.end){
                throw new mod.StopIteration();
            }else{
                this.current = this.current + this.step;
                return this.current;
            }
        }
    })
    
    Range = mod.Range;
    
    /**
        Iterator for Arrays.
    */
    mod.ArrayItereator=Class(mod.Iterator, function(publ, supr){
        publ.init=function(array){
            this.array = array;
            this.index = -1;
        }
        publ.next = function(){
            this.index += 1;
            if(this.index >= this.array.length){
                throw new mod.StopIteration();
            }
            return this.array[this.index];
        }
    })
    
    Array.prototype.iterator = function(){
        return new mod.ArrayItereator(this);
    }
        
    /**
        Interface of a IterationCallback.
        @param item The item returned by the iterator for the current step.
        @param iteration The Iteration object handling the iteration.
    */
    mod.IterationCallback = function(item, iteration){};
    
    /**
        Iteration class for handling iteration steps and callbacks.
    */
    mod.Iteration = Class(function(publ, supr){
        /**
            Initializes an Iteration object.
            @param iteratable An itaratable object.
            @param callback An IterationCallback object.
        */
        publ.init=function(iteratable, callback){
            this.doStop = false;
            this.iterator = iteratable.iterator();
            this.callback = callback;
        }
        
        ///Resumes a paused/stoped iteration.
        publ.resume = function(){
            this.doStop = false;
            while(!this.doStop){
                this.handleStep();
            }
        }
        ///Pauses an iteration.      
        publ.pause=function(){
            this.doStop = true;
        }
        ///Stops an iteration
        publ.stop = function(){
            this.pause();
        }
        ///Starts/resumes an iteration        
        publ.start = function(){
            this.resume();
        }
        
        ///Handles a single iteration step calling the callback with the next item or terminating.
        publ.handleStep = function(){
            try{//to get the next item
                var item=this.iterator.next();
            }catch(e){
                if(e.constructor != mod.StopIteration){
                    throw e; //was a different error in the iterator, so throw it
                }else{
                    this.stop(); //this is the end of the iteration
                    return;
                }
            }
            //let the callback handle the item
            this.callback(item, this);
        }
    })
    
    /**
        Class for handling asynchronous iterations.
    */
    mod.AsyncIteration = Class(mod.Iteration, function(publ, supr){
        /**
            Initializes an AsyncIteration object.
            @param iteratable An itaratable object.
            @param interval The time in ms betwen each step.
            @param callback An IterationCallback object.
        */
        publ.init=function(iteratable, interval, callback){
            if(arguments.length == 2){
                callback = interval;
                interval = 0;
            }
            this.iterator = iteratable.iterator();
            this.interval = interval;
            this.callback = callback;
            this.isRunning = false;
        }
        
        publ.pause=function(){
            if(this.isRunning){
                this.isRunning = false;
                clearTimeout(this.timeout);    
                delete fora.iterations[this.id];
            }
        }
        
        publ.resume = function(){
            if(this.isRunning == false){
                this.isRunning = true;
                var id=0;//find unused id
                while(fora.iterations[id]){
                    this.id++;
                }
                this.id = "" + id;
                fora.iterations[this.id] = this;
                //let the iteration be handled using a timer
                this.timeout = setTimeout("fora.handleAsyncStep('" + this.id + "')", this.interval);
            }
        }
        
        publ.handleAsyncStep = function(){
            if(this.isRunning){
                this.handleStep();
                this.timeout = setTimeout("fora.handleAsyncStep('" + this.id + "')", this.interval);
            }
        }
    })
    
    /**
        Asynchronous iteration function.
        This function returns immidiately and executes each iteration step asynchronously.
        @param iteratable An iteratable object.
        @param interval=0 The interval time in ms for each iteration step.
        @param cb The IterationCallback which is called for each itereation step.
        @return An AsyncIteration object.
    */
    fora = function(iteratable, interval, cb){
        if(arguments.length==2){
            var it = new mod.AsyncIteration(iteratable, interval);
        }else{
            var it = new mod.AsyncIteration(iteratable, interval, cb);      
        }
        it.start();
        return it;
    }
    
    fora.handleAsyncStep = function(id){
        if(fora.iterations[id]){
           fora.iterations[id].handleAsyncStep();
        }
    }
    ///Helper object containing all async. iteration objects.
    fora.iterations = new Object();

    /**
        Iterates over an Iteratable object and calls a callback for each item.
        @param iteratable The iteratable object.
        @param cb       An IterationCallback object to call for each step.
    */
    forin = function(iteratable, cb){
        var it = new mod.Iteration(iteratable, cb)
        it.start();
    }
    
    mod.test=function(){
        forin(new mod.Range(10), function(item,i){
            print(item);
            
        })
        forin([1,2,3,4,5,6], function(item,i){
            print(item);
            print("---")
        })
    }
})

