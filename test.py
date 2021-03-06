# -*- coding: utf-8 -*-
import asyncio
import json
import requests
import os
import time
import urllib
import queue
import threading
import platform
import logging
from aiowebsocket.converses import AioWebSocket
from requests.adapters import HTTPAdapter


models = {'Virgin_Emma':'126192483','Ulla996':'123371138'}
status =  {'Virgin_Emma':0,'Ulla996':0}#0表示未下载，1表示正在下载
gLock = threading.Lock()

def creat_file(path):
    for model in models:
        path1 = path + model
        if not os.path.isdir(path1):
            os.makedirs(path1)
    
def del_file(path):
    for i in os.listdir(path):
        path_file = os.path.join(path,i)
        if os.path.isfile(path_file):
            os.remove(path_file)
        else:
            del_file(path_file)


async def startup(uri):
    strs = 'respkey'
    ol_model = queue.Queue()
    ol_url = queue.Queue()
    async with AioWebSocket(uri) as aws:
        converse = aws.manipulator
        await converse.send('1 0 0 20080910 0 ::WyJ5dXpob3VnZSIsIkFuNmpieUh0SElHZGVVNU5TdVdpemV6Q3RjQ3Z3QTVLIiwiMSJd'+'\n')
        while True:
            mes = await converse.receive()
            mes = str(mes, encoding = "utf-8")
            mes = urllib.parse.unquote(mes)
            if strs in mes:
                first_num = mes.find('}')
                mes = mes[first_num:]
                last_num = mes.find('14}') + 3
                mes = mes[:last_num]
                mes = mes.replace('},','{')
                mes_json = json.loads(mes)
                fcw_url = 'https://www.myfreecams.com/php/FcwExtResp.php?type=14&opts=256&respkey=' + str(mes_json["respkey"]) + '&serv=' + str(mes_json["serv"])
                print(fcw_url)
                print(time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime()))
                while True:
                    fcw_data = request_get(fcw_url)
                    if fcw_data.status_code == 200:
                        fcw = fcw_data.text
                        break
                fcw_json = json.loads(fcw)
                if fcw_json['type'] != 21:
                    continue
                config_url='https://www.myfreecams.com/_js/serverconfig.js'
                while True:
                    config_data = request_get(config_url)
                    if config_data.status_code == 200:
                        config = config_data.text
                        break
                for model in models:
                    if status[model] == 0:
                        if fcw.find(model) != -1:
                            i = 0
                            while True:
                                if fcw_json["rdata"][i][0] == model:
                                    break
                                else:
                                    i = i + 1
                            print(fcw_json["rdata"][i][0])
                            videoid = fcw_json["rdata"][i][6]
                            config_json = json.loads(config)
                            videoser = config_json["h5video_servers"][str(videoid)]
                            playlisturl = 'https://' + videoser + '.myfreecams.com/NxServer/ngrp:mfc_' + models.get(model) + '.f4v_mobile/playlist.m3u8'
                            res = request_get(playlisturl)
                            if res.status_code == 200 and status[model] == 0:
                                print(model + ' is online')
                                chunklist = dels(res.text.splitlines())
                                url = ''
                                for s in chunklist:
                                    if 'chunklist' in s:
                                        strlist = s.split('_')
                                        if '256' in strlist[-1]:                                          
                                            url = 'https://' + videoser + '.myfreecams.com/NxServer/ngrp:mfc_' + models.get(model) + '.f4v_mobile/'+ s
                                            #url = 'https://' + videoser + '.myfreecams.com/NxServer/ngrp:mfc_a_' + models.get(model) + '.f4v_mobile/'+ s
                                            break
                                        else:
                                            url = 'https://' + videoser + '.myfreecams.com/NxServer/ngrp:mfc_' + models.get(model) + '.f4v_mobile/'+ s
                                            #url = 'https://' + videoser + '.myfreecams.com/NxServer/ngrp:mfc_a_' + models.get(model) + '.f4v_mobile/'+ s
                                if 'http' in url:
                                    ol_model.put(model)
                                    ol_url.put(url)
                                else:
                                    print('未获得chunklist')
                            else:
                                print(res)
                        else:
                            print(model + ' is offline')
                return ol_model,ol_url
                break



def geturl(url,num):
    downurl = queue.Queue()
    res = request_get(url)
    savenum = []
    if res.status_code == 200:
        temp = res.text.splitlines()
        temp = dels(temp)
        for i in temp:
            currentnum = findnum(i)
            if currentnum > num:
                k = url[0:url.rfind('/') + 1] + i               
                downurl.put(k)
                savenum.append(currentnum)
    else:
        print(url+'m3u8列表已经失效,错误代码'+str(res.status_code))
    return downurl,savenum

def dels(list):
    b = list[:]
    for i in list:
        if '#'in i:
            b.remove(i)
    list = b
    return list

def maindown(url,model):
    print('准备下载'+model)
    file = temppath + model + '/'
    file1 = savepath + model + '/'
    if request_get(url).status_code == 200:
        request_post(model,'开始下载')
        status[model] = 1
        print('正在下载'+ model)
        print('TS下载完成')
        now = time.strftime("%Y-%m-%d-%H_%M", time.localtime())
        cmd = 'ffmpeg -safe 0 -i '+ url+' -vcodec copy -acodec copy '+ file1 + str(now) +'.ts'
        result = os.system(cmd)
        print(result)
        status[model] = 0
        request_post(model,'合并完成')
            
    else:
        print('m3u8连接失败')     

class download(threading.Thread):#下载程序
    def __init__(self,que,file):
        threading.Thread.__init__(self)
        self.que = que
        self.file = file
    def run(self):
        self.result = []
        while True:
            if not self.que.empty():
                url = self.que.get()
                r = request_get(url)
                if r.status_code == 200:
                    num = findnum(url)
                    with open(self.file + str(num)  + '.ts','wb') as a:
                        a.write(r.content)
                    self.result.append(num)
                    print('已下载' + str(findnum(url)))
                else:
                    print(url + 'TS文件' + str(r.status_code))
            else:
                break
    def get_result(self):
        return self.result


def findnum(url):#获取TS链接的序号num
    start = url.rfind('_') + 1
    end = url.rfind('.ts')
    num = url[start:end]
    num = int(num)
    return num

def request_get(url):
    s = requests.Session()
    s.mount('http://', HTTPAdapter(max_retries=3))
    s.mount('https://', HTTPAdapter(max_retries=3))
    r = s.get(url)
    return r

def request_post(model,text):
    try:
        requests.post(api+model+text)
    except:
        print(model+text)
    

if __name__ == '__main__':
    sys = platform.system()
    if sys == "Windows":
        temppath = 'e:/temp/'
        savepath = 'e:/video/'
    else:
        temppath = '/root/temp/'
        savepath = '/root/video/'
    remote = 'wss://xchat72.myfreecams.com/fcsl'
    api = "https://sc.ftqq.com/SCU84034T4390e074a26e7a7ed66427692ac0a7b65e48f3b1d85ee.send?text="
    creat_file(temppath)
    creat_file(savepath)
    try:
        while True:
            model_ol,url_ol = asyncio.get_event_loop().run_until_complete(startup(remote))
            if not model_ol.empty():
                threads = []
                num = model_ol.qsize()
                for i in range(num):
                    d = threading.Thread(target=maindown,args = [url_ol.get(),model_ol.get()])
                    threads.append(d)
                for d in threads:
                    d.start()
            time.sleep(600)
            
    except KeyboardInterrupt as exc:
        logging.info('Quit.')

