#!/bin/python3
import os
import random
import re
import string
import time
import itertools
import json
#import pprofile

#virtual terminal control codes:
#https://docs.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences

#https://theasciicode.com.ar/ascii-control-characters/null-character-ascii-code-0.html
batch_input_compensation_enabled = 1
batch_input_compensation_threshold = 0.01 #seconds, 0.01 (10ms) was chosen because a human with talon voice cannot have that result. but this is getting close to fast keyboard speeds
elimination_threshold = 3 #how many times in a row you must get this right (with perfect speed before a char is eliminated)
recall_threshold = 1 #seconds to recall and input a correct value before penalties apply
batch = 10 #number of character that will be displayed at one time.
#batch size is important to be somewhat small if you are dictating with talonvoice.
#this is because when you go fast talon will start to batch your input.
training_set_letters = string.ascii_lowercase #training character set
training_set_symbols = ".,?!:;`'\"{}()[]<>=_-+*#/\$%^&|@~"
training_set=training_set_letters
training_deck=[x for x in training_set]
random.shuffle(training_deck)
training_set = ''.join(training_deck)

#source: http://stackoverflow.com/a/21659588/344286
def _find_getch():
    try:
        import termios
    except ImportError:
        # Non-POSIX. Return msvcrt's (Windows') getch.
        import msvcrt
        return msvcrt.getch

    # POSIX system. Create and return a getch that manipulates the tty.
    import sys, tty
    def _getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        if ord(ch) == 3:
            raise KeyboardInterrupt('^C entered')
        elif ord(ch) == 4:
            pass
            #raise EOFError('^D entered')
        return ch

    return _getch

getch = _find_getch()

def clamp(n,nmin,nmax):
    return max(min(n,nmax),nmin)

def color(r,g,b):
    return "\033[38;2;{};{};{}m".format(r,g,b)
def gradient_green_red(p):
    r=int(255*p)
    g=int(255*(1-p))
    return color(int(r),int(g),0)
def gradient_red(p):
    r=int(255*p)
    return color(int(r),0,0)

def next_line(stats,threshold):
    result_max_length=batch
    untried=''
    for j in stats.keys():
        if stats[j][0] == 0:
            untried=untried+j
    result=untried[0:result_max_length]
    if len(result)<result_max_length:
        high_score_dict=sorted(stats.items(), key=lambda x:x[1][3], reverse=True )
        for k,v in high_score_dict:
            if v[3] > pow(.5,threshold) and len(result)<result_max_length and v[0] !=0:
                result+=k
        #expirimental
        ##if we do not have even 75% of a batch fill it with a looser threshold.
        ##This will re expose already dropped off variables but will allow for a
        ##less repetitive practice.
        #if len(result) < result_max_length * .75 :
        #    threshold-=4
        #    for k,v in high_score_dict:
        #        if v[3] > pow(.5,threshold) and len(result)<result_max_length:
        #            result+=k
    deck=[x for x in result]
    random.shuffle(deck)
    return ''.join(deck)

def print_scores(sts):
    chars=''.join([x for x in sts.keys()])
    prefix_length=9
    f="#"*(len(chars)+ prefix_length + 2)
    h="STATS".center(len(f),'#',) + ""
    r="# char : " + chars + " #"
    s=c=e=''
    for i in chars:
        # Show truncated scores as hex to represent as a single char
        # since a score max is 1, multiply by 16 to get the full range of hex values
        s=s+"{}{:X}".format(gradient_green_red(float(sts[i][3])),int(sts[i][3]*16-.0001))
        c=c+"{:X}".format(sts[i][0])
        e=e+"{}{:X}".format(gradient_red(clamp(sts[i][1]/16,.6,1)),sts[i][1])
    s='# score: {}\033[0m #'.format(s)
    c='# count: {} #'.format(c)
    e='# error: {}\033[0m #'.format(e)
    #print(h,r,s,c,e,f,sep='\n')
    print(h,r,s,c,e,f,sep='\n')

def train_line(line):
    bstats={}
    for i in line:
                 #[error,time]
        bstats[i]=[0    ,0   ]
    i=0
    while(i<len(line)):
        print(line[i:].ljust(30,' ') + ' ' * i, end='\n')
        control('eraseline')
        start=time.time()
        input_char=getch() #get input
        #input_char=random.choices( [line[i], 'A'], weights=[.95,.05] )[0] #pretend to hold down the 'a' key
        #time.sleep(random.randrange(0,1))
        end=time.time()

        if (line[i] != input_char): #if there was an error
            bstats[line[i]][0]=1 #increment error counter
        bstats[line[i]][1]=end-start

        i=i+1
        control('eraseline')
        control('up1')

    #control('eraseline')
    control('clear')
    return bstats

def batch_input_comp(bstats,threshold):
    last_human_input = 0
    keys=''.join(bstats.keys())
    j=0
    while (j<len(keys)):
        if (bstats[keys[j]][1] > threshold and j != last_human_input):
            last_human_input_speed=bstats[keys[last_human_input]][1]
            if (j == 0):
                last_human_input_speed*=0.75 #if this is the first item in the batch reduce input speed because this letter has an unfair disadvantage
            inputs_since_last_human_input=j-last_human_input
            average_human_input_speed=last_human_input_speed/inputs_since_last_human_input
            while (last_human_input < j):
                bstats[keys[last_human_input]][1]=average_human_input_speed
                last_human_input+=1
            last_human_input=j
        elif (bstats[keys[j]][1] < threshold and j + 1 == len(keys)):
            last_human_input_speed=bstats[keys[last_human_input]][1]
            inputs_since_last_human_input=j-last_human_input + 1
            average_human_input_speed=last_human_input_speed/inputs_since_last_human_input
            while (last_human_input <= j):
                bstats[keys[last_human_input]][1]=average_human_input_speed
                last_human_input+=1

        j+=1
    return bstats

def control(code):
    codes = {
      'clear': '\033[H\033[2J', #go home; clear screen
      'eraseline': '\033[2K',
      'up1': '\033[1A',
      'down1': '\033[1B'
    }
    print(codes[code],end='')

def teach(chars):
    control('clear')
    stats={}
    for i in chars:
                #[count,errors,time,score]
        stats[i]=[0    ,0     ,0   ,1    ]
    line=next_line(stats,elimination_threshold)
    while(len(line) > 0):
        #print("### STATUS: CPM: {cpm:n} Accuracy: {accuracy:.2f} ###".format(cpm=0,accuracy=0))
        print_scores(stats)

        batch_stats=train_line(line)

        #if a software like talonvoice is used it will batch input if the
        #user speaks quickly so we compensate for it
        if batch_input_compensation_enabled == 1:
            batch_stats=batch_input_comp(batch_stats,batch_input_compensation_threshold)

        #update stats
        for k,v in batch_stats.items():
            stats[k][0]+=1 #update count
            stats[k][3]/=2 #decay the score
            if (v[0]): #if there was an error
                stats[k][1]+=1 #increment error counter
                stats[k][3]=1 #set score to max

            stats[k][2]+=v[1]
            if v[1] > recall_threshold:
                stats[k][3]+=.2*v[1]/recall_threshold #for every threshold increment the score by 20%
                if stats[k][3] > 1: #if the score is over 100%
                    stats[k][3] = 1 #set the score to 100%

        control('up1')
        line=next_line(stats,elimination_threshold)
    print_scores(stats)
    file=str(int(time.time())) + '.json'
    with open(file,"w") as outfile:
        json.dump(stats,outfile,indent=2)

if __name__ == '__main__':
    #prof=pprofile.Profile()
    #with prof():
    #  teach(training_set)
    #prof.print_stats()
    teach(training_set)
