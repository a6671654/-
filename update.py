import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'gupiao.settings'
import django
django.setup()
from main import models
import pandas as pd
import time
import baostock as bs
import datetime
import talib
import togmail
import tushare as ts

def jsline(a):
    a['DIF'], a['DEA'], a['hist'] = talib.MACD(a['close'], fastperiod=12, slowperiod=26, signalperiod=9)
    df_status = a
    low = df_status['low'].astype(float)
    del df_status['low']
    df_status.insert(0, 'low', low)
    high = df_status['high'].astype(float)
    del df_status['high']
    df_status.insert(0, 'high', high)
    close = df_status['close'].astype(float)
    del df_status['close']
    df_status.insert(0, 'close', close)
    low_list = df_status['low'].rolling(window=9).min()
    high_list = df_status['high'].rolling(window=9).max()
    rsv = (df_status['close'] - low_list) / (high_list - low_list) * 100
    a['K'] = rsv.ewm(com=2).mean()
    a['D'] = a['K'].ewm(com=2).mean()
    a['J'] = 3 * a['K'] - 2 * a['D']
    a['EMA12'] = talib.EMA(a['close'], timeperiod=12)
    a['EMA26'] = talib.EMA(a['close'], timeperiod=26)
    a['5day'] = talib.SMA(a['close'], timeperiod=5)
    a['10day'] = talib.SMA(a['close'], timeperiod=10)
    a['20day'] = talib.SMA(a['close'], timeperiod=20)
    a['upper'], a['middle'], a['lower'] = talib.BBANDS(a['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    a['EMA12'] = talib.EMA(a['close'], timeperiod=12)
    a['EMA26'] = talib.EMA(a['close'], timeperiod=26)
    return a

def onedateup(codename,open_csv,rs):
    rs=rs.set_index('date')
    new_csv=open_csv.append(rs.iloc[0])
    new_csv=jsline(new_csv).tail(1)
    new_csv['EMA12'] = (new_csv['close'] * 2 + (open_csv['EMA12'].iloc[-1]) * 11) / 13
    new_csv['EMA26'] = (new_csv['close'] * 2 + (open_csv['EMA26'].iloc[-1]) * 25) / 27
    new_csv['DIF'] = new_csv['EMA12'] - new_csv['EMA26']
    new_csv['DEA'] = (new_csv['DIF'] * 2 + (open_csv['DEA'].iloc[-1]) * 8) / 10
    new_csv['hist'] = new_csv['DIF'] - new_csv['DEA']
    open_csv=pd.concat([open_csv,new_csv],sort=False)
    if len(open_csv.index)>90:
        open_csv=open_csv.tail(90)
    elif len(open_csv.index)<60:
        print(codename,'数据内容过短，建议删除')
        togmail.send('254370469@qq.com','codename数据过短','建议删除对应股票')
    open_csv.to_csv(f'/root/gupiao/try/{codename}.csv')
    open_csv=pd.read_csv(f'/root/gupiao/try/{codename}.csv',index_col=0)
    return open_csv


def goodjob(codename,newday):
    btime=str(newday-datetime.timedelta(days=250))
    otime=str(newday)
    rs = bs.query_history_k_data_plus(i,"date,open,high,low,close,preclose,volume,amount,turn,tradestatus,pctChg,isST,peTTM,psTTM,pcfNcfTTM,pbMRQ",start_date=btime, end_date=otime).get_data()
    a=rs
    a.to_csv(f'/root/gupiao/try/{codename}.csv',index=False)
    time.sleep(1)
    a=pd.read_csv(f'/root/gupiao/try/{codename}.csv',index_col=0)
    a=a[a['tradestatus']==1]
    if len(a.index)>50:
        a=jsline(a)
    else:
        print(codename,'长度不够，不计算数据请从列表中删除')
    a.to_csv(f'/root/gupiao/try/{codename}.csv')
    print(codename,'重新下载数据完成')
    return a

def zhibiao(newday):
    print('正在下载每日指标数据')
    pro = ts.pro_api()
    newday=newday.replace('-','')
    zhibiaodf = pro.daily_basic(ts_code='', trade_date=newday,fields='ts_code,trade_date,volume_ratio,pe,pb,ps,float_share,total_mv,circ_mv')
    zhibiaodf = zhibiaodf.where(zhibiaodf.notnull(), None)
    print('每日指标数据下载完成')
    return zhibiaodf

def danzhibiao(zhibiaodf,i):
    tscode = i.split('.')
    tscode = tscode[1] + '.' + tscode[0].upper()
    lszhibiao = zhibiaodf[zhibiaodf['ts_code'] == tscode].iloc[0]
    return lszhibiao

lg = bs.login()
if datetime.datetime.now().hour >= 17:
    nowday=datetime.datetime.now().date()
else:
    nowday=datetime.datetime.now().date()-datetime.timedelta(days=1)
newday = models.Jiaoyiday.objects.last().date
print('最新数据为',newday,'今天是',nowday,'准备开始更新')
if newday>=nowday:
    togmail.send('254370469@qq.com','股票更新报错',f'最新日期是{newday}，现在需要更新的日期是{nowday}，不需要更新，直接退出')
    raise Exception(f'最新日期是{newday}，现在需要更新的日期是{nowday}，不需要更新，直接退出')

rs = bs.query_trade_dates(start_date=str(newday), end_date=str(nowday))
date_list=[]
while (rs.error_code == '0') & rs.next():
    date_list.append(rs.get_row_data())

for daylist in date_list[1:]:
    if daylist[1]=='1':
        newday=daylist[0]
        print(newday,'是交易日，开始更新。。。')
        zhibiaodf=zhibiao(newday)
        c=models.Jiaoyiday(date=newday,isover=False)
        c.save()
        n=0
        gupiaolist = models.Gupiaolist.objects.all()
        tiaoguolist=[]
        for ii in gupiaolist:
            i=ii.code
            try:
                rs = bs.query_history_k_data_plus(i,"date,open,high,low,close,preclose,volume,amount,turn,tradestatus,pctChg,isST,peTTM,psTTM,pcfNcfTTM,pbMRQ",start_date=newday, end_date=newday).get_data()
                if int(rs['tradestatus'].iloc[0]) != 1:
                    print(i,newday,'停牌，跳过')
                    tiaoguolist.append({i:'停牌'})
                    continue
            except:
                print(i,newday,'获取单日出错直接跳过')
                tiaoguolist.append({i:'获取出错'})
                continue
            lastclose = float(rs['preclose'].iloc[0])
            try:
                open_csv = pd.read_csv(f'/root/gupiao/try/{i}.csv',index_col=0)###如果没有，重下
            except:
                print('检测到没有',i,'数据文件，准备重新创建并覆盖')
                open_csv=goodjob(i,(datetime.datetime.strptime(newday,'%Y-%m-%d').date()-datetime.timedelta(days=1)))
            lastline=open_csv.tail(1)
            if lastclose == lastline['close'].iloc[0]:
                #相等
                open_csv = onedateup(i,open_csv, rs)
            else:
                # 不相等 重下数据
                print('收盘价对不上，重新下载',i,'的数据')
                open_csv=goodjob(i,datetime.datetime.strptime(newday,'%Y-%m-%d').date())

            #写入数据库
            if len(open_csv.index)>30 and open_csv.index[-1] == newday:
                a=open_csv.iloc[-1]
                lszhibiao=danzhibiao(zhibiaodf,i)
                try:
                    obj = models.Kline(code=ii, date=c, open=a['open'], close=a['close'],
                                       high=a['high'], low=a['low'], volume=a['volume'],
                                       turn=a['turn'], preclose=a['preclose'], dif=a['DIF'],
                                       dea=a['DEA'], hist=a['hist'], kdjK=a['K'], kdjD=a['D'],
                                       kdjJ=a['J'], day5=a['5day'], day10=a['10day'],
                                       day20=a['20day'], upper=a['upper'], middle=a['middle'], lower=a['lower'],
                                       volume_ratio=lszhibiao['volume_ratio'], pe=lszhibiao['pe'], pb=lszhibiao['pb'],
                                       ps=lszhibiao['ps'], float_share=lszhibiao['float_share'],total_mv=lszhibiao['total_mv'],
                                       circ_mv=lszhibiao['circ_mv'])
                    obj.save()
                except Exception as E:
                    print(i,newday,'写入报错')
                    print(E)
                    continue
                a=open_csv
                buymean20 = (a['volume'].iloc[-21:-1].mean())
                buymean5 = (a['volume'].iloc[-6:-1].mean())
                jihelist = []
                if a['volume'].iloc[-1] > buymean20*2:
                    jihelist.append('buynum20=True')
                elif a['volume'].iloc[-1] < buymean20*0.5:
                    jihelist.append('buynum20=False')
                if a['volume'].iloc[-1] > buymean5*2:
                    jihelist.append('buynum5=True')
                elif a['volume'].iloc[-1] < buymean5*0.5:
                    jihelist.append('buynum5=False')
                if a['hist'].iloc[-1] > 0 and a['hist'].iloc[-2] < 0:
                    jihelist.append('MACD=True')
                elif a['hist'].iloc[-1] < 0 and a['hist'].iloc[-2] > 0:
                    jihelist.append('MACD=False')
                if a['5day'].iloc[-1] > a['10day'].iloc[-1] and a['5day'].iloc[-2] < a['10day'].iloc[-2]:
                    jihelist.append('day5to10=True')
                elif a['5day'].iloc[-1] < a['10day'].iloc[-1] and a['5day'].iloc[-2] > a['10day'].iloc[-2]:
                    jihelist.append('day5to10=False')
                if a['5day'].iloc[-1] > a['20day'].iloc[-1] and a['5day'].iloc[-2] < a['20day'].iloc[-2]:
                    jihelist.append('day5to20=True')
                elif a['5day'].iloc[-1] < a['20day'].iloc[-1] and a['5day'].iloc[-1] > a['20day'].iloc[-1]:
                    jihelist.append('day5to20=False')
                if a['10day'].iloc[-1] > a['20day'].iloc[-1] and a['10day'].iloc[-1] < a['20day'].iloc[-1]:
                    jihelist.append('day10to20=True')
                elif a['10day'].iloc[-1] < a['20day'].iloc[-1] and a['10day'].iloc[-2] > a['20day'].iloc[-2]:
                    jihelist.append('day10to20=False')
                if a['volume'].iloc[-1] > a['volume'].iloc[-2] * 2:
                    jihelist.append('buynumtwo=True')
                elif a['volume'].iloc[-1] < a['volume'].iloc[-2] * 0.5:
                    jihelist.append('buynumtwo=False')
                if a['K'].iloc[-1] > a['D'].iloc[-1] and a['K'].iloc[-2] < a['D'].iloc[-2]:
                    jihelist.append('KDJ=True')
                elif a['K'].iloc[-1] < a['D'].iloc[-1] and a['K'].iloc[-2] > a['D'].iloc[-2]:
                    jihelist.append('KDJ=False')
                if a['volume'].iloc[-1]>a['volume'].iloc[-2]:
                    if a['volume'].iloc[-2] > a['volume'].iloc[-3]:
                        if a['volume'].iloc[-3] > a['volume'].iloc[-4]:
                            jihelist.append('buynum3up=True')
                            if a['volume'].iloc[-4] > a['volume'].iloc[-5] and a['volume'].iloc[-5] > a['volume'].iloc[-6]:
                                jihelist.append('buynum5up=True')
                    else:
                        if a['volume'].iloc[-3] < a['volume'].iloc[-4] and  a['volume'].iloc[-4] < a['volume'].iloc[-5]:
                            jihelist.append('buynum3chang=False')
                            if a['volume'].iloc[-5] < a['volume'].iloc[-6] and  a['volume'].iloc[-6] < a['volume'].iloc[-7]:
                                jihelist.append('buynum5chang=False')
                else:
                    if a['volume'].iloc[-2] < a['volume'].iloc[-3]:
                        if a['volume'].iloc[-3] < a['volume'].iloc[-4]:
                            jihelist.append('buynum3up=False')
                            if a['volume'].iloc[-4] < a['volume'].iloc[-5] and a['volume'].iloc[-5] < a['volume'].iloc[-6]:
                                jihelist.append('buynum5up=False')
                    else:
                        if a['volume'].iloc[-3] > a['volume'].iloc[-4] and  a['volume'].iloc[-4] > a['volume'].iloc[-5]:
                            jihelist.append('buynum3chang=True')
                            if a['volume'].iloc[-5] > a['volume'].iloc[-6] and  a['volume'].iloc[-6] > a['volume'].iloc[-7]:
                                jihelist.append('buynum5chang=True')
                if a['5day'].iloc[-5:].max()< a['5day'].iloc[-5:].min()*1.03:
                    jihelist.append('day5keep5=True')
                if a['5day'].iloc[-10:].max()< a['5day'].iloc[-10:].min()*1.05:
                    jihelist.append('day5keep10=True')
                if a['5day'].iloc[-20:].max()< a['5day'].iloc[-20:].min()*1.1:
                    jihelist.append('day5keep20=True')
                if a['hist'].iloc[-1]>a['hist'].iloc[-2]:
                    if a['hist'].iloc[-2] > a['hist'].iloc[-3]:
                        if a['hist'].iloc[-3] > a['hist'].iloc[-4]:
                            jihelist.append('MACD3up=True')
                            if a['hist'].iloc[-4] > a['hist'].iloc[-5] and a['hist'].iloc[-5] > a['hist'].iloc[-6]:
                                jihelist.append('MACD5up=True')
                        else:
                            if a['hist'].iloc[-4] < a['hist'].iloc[-5] and a['hist'].iloc[-5] < a['hist'].iloc[-6]:
                                jihelist.append('MACD3chang2=False')
                                if a['hist'].iloc[-6] < a['hist'].iloc[-7] and a['hist'].iloc[-7] < a['hist'].iloc[-8]:
                                    jihelist.append('MACD5chang2=False')
                    else:
                        if a['hist'].iloc[-3] < a['hist'].iloc[-4] and  a['hist'].iloc[-4] < a['hist'].iloc[-5]:
                            jihelist.append('MACD3chang=False')
                            if a['hist'].iloc[-5] < a['hist'].iloc[-6] and  a['hist'].iloc[-6] < a['hist'].iloc[-7]:
                                jihelist.append('MACD5chang=False')
                else:
                    if a['hist'].iloc[-2] < a['hist'].iloc[-3]:
                        if a['hist'].iloc[-3] < a['hist'].iloc[-4]:
                            jihelist.append('MACD3up=False')
                            if a['hist'].iloc[-4] < a['hist'].iloc[-5] and a['hist'].iloc[-5] < a['hist'].iloc[-6]:
                                jihelist.append('MACD5up=False')
                        else:
                            if a['hist'].iloc[-4] > a['hist'].iloc[-5] and a['hist'].iloc[-5] > a['hist'].iloc[-6]:
                                jihelist.append('MACD3chang2=True')
                                if a['hist'].iloc[-6] > a['hist'].iloc[-7] and a['hist'].iloc[-7] > a['hist'].iloc[-8]:
                                    jihelist.append('MACD5chang2=True')
                    else:
                        if a['hist'].iloc[-3] > a['hist'].iloc[-4] and  a['hist'].iloc[-4] > a['hist'].iloc[-5]:
                            jihelist.append('MACD3chang=True')
                            if a['hist'].iloc[-5] > a['hist'].iloc[-6] and  a['hist'].iloc[-6] > a['hist'].iloc[-7]:
                                jihelist.append('MACD5chang=True')
                a['chazhi']=a['upper']-a['lower']
                if a['chazhi'].iloc[-1]> a['chazhi'].iloc[-2]:
                    if a['chazhi'].iloc[-2]>a['chazhi'].iloc[-3] and a['chazhi'].iloc[-3]>a['chazhi'].iloc[-4]:
                        jihelist.append('BOLL3big=True')
                        if a['chazhi'].iloc[-4]>a['chazhi'].iloc[-5] and a['chazhi'].iloc[-5]>a['chazhi'].iloc[-6]:
                            jihelist.append('BOLL5big=True')
                else:
                    if a['chazhi'].iloc[-2]<a['chazhi'].iloc[-3] and a['chazhi'].iloc[-3]<a['chazhi'].iloc[-4]:
                        jihelist.append('BOLL3big=False')
                        if a['chazhi'].iloc[-4]<a['chazhi'].iloc[-5] and a['chazhi'].iloc[-5]<a['chazhi'].iloc[-6]:
                            jihelist.append('BOLL5big=False')
                lianyang=0
                if a['close'].iloc[-1]>a['open'].iloc[-1]:
                    for mostday in range(1,8):
                        if a['close'].iloc[-mostday] > a['open'].iloc[-mostday]:
                            lianyang = mostday
                        else:
                            break
                    # if a['close'].iloc[-2]>a['open'].iloc[-2] and a['close'].iloc[-3]>a['open'].iloc[-3]:
                    #     lianyang=3
                    #     if a['close'].iloc[-4]>a['open'].iloc[-4] and a['close'].iloc[-5]>a['open'].iloc[-5]:
                    #         lianyang=5
                    #         if a['close'].iloc[-6] > a['open'].iloc[-6] and a['close'].iloc[-7] > a['open'].iloc[-7]:
                    #             lianyang = 7
                elif a['close'].iloc[-1]<a['open'].iloc[-1]:
                    for mostday in range(1,8):
                        if a['close'].iloc[-mostday] < a['open'].iloc[-mostday]:
                            lianyang = -mostday
                        else:
                            break
                    # if a['close'].iloc[-2]<a['open'].iloc[-2] and a['close'].iloc[-3]<a['open'].iloc[-3]:
                    #     lianyang = -3
                    #     if a['close'].iloc[-4]<a['open'].iloc[-4] and a['close'].iloc[-5]<a['open'].iloc[-5]:
                    #         lianyang = -5
                    #         if a['close'].iloc[-6] < a['open'].iloc[-6] and a['close'].iloc[-7] < a['open'].iloc[-7]:
                    #             lianyang = -7
                if lianyang != 0:
                    jihelist.append('yang=lianyang')

                lianzhang = 0
                if a['close'].iloc[-1] > a['preclose'].iloc[-1]:
                    for mostday in range(1, 8):
                        if a['close'].iloc[-mostday] > a['preclose'].iloc[-mostday]:
                            lianzhang = mostday
                        else:
                            break
                    # if a['close'].iloc[-2] > a['preclose'].iloc[-2] and a['close'].iloc[-3] > a['preclose'].iloc[-3]:
                    #     lianzhang = 3
                    #     if a['close'].iloc[-4] > a['preclose'].iloc[-4] and a['close'].iloc[-5] > a['preclose'].iloc[-5]:
                    #         lianzhang = 5
                    #         if a['close'].iloc[-6] > a['preclose'].iloc[-6] and a['close'].iloc[-7] > a['preclose'].iloc[-7]:
                    #             lianzhang = 7
                elif a['close'].iloc[-1] < a['preclose'].iloc[-1]:
                    for mostday in range(1, 8):
                        if a['close'].iloc[-mostday] < a['preclose'].iloc[-mostday]:
                            lianzhang = -mostday
                        else:
                            break
                    # if a['close'].iloc[-2] < a['preclose'].iloc[-2] and a['close'].iloc[-3] < a['preclose'].iloc[-3]:
                    #     lianzhang = -3
                    #     if a['close'].iloc[-4] < a['preclose'].iloc[-4] and a['close'].iloc[-5] < a['preclose'].iloc[-5]:
                    #         lianzhang = -5
                    #         if a['close'].iloc[-6] < a['preclose'].iloc[-6] and a['close'].iloc[-7] < a['preclose'].iloc[-7]:
                    #             lianzhang = -7
                if lianzhang != 0:
                    jihelist.append('zhang=lianzhang')

                if len(jihelist) > 0:
                    zxnr = ''
                    for nrlist in jihelist:
                        zxnr = zxnr + nrlist + ','
                    zxnr = zxnr[:-1]
                    ojc = eval(f'models.Jisuan(dayline=obj,{zxnr})')
                    ojc.save()
            else:
                print(i,'数据行数不够或者日期不对，跳过')
                tiaoguolist.append({i:'行数不够或者日期不对'})
                continue
            n+=1
            if n % 500 == 499:
                bs.logout()
                print('已完成500，休息15秒')
                time.sleep(15)
                lg = bs.login()
        bt=f'{newday}更新完成,共更新{n}条数据'
        c.isover=True
        c.save()
        if len(gupiaolist)>n:
            nr='有部分股票没更新成功\n'
            nr=nr+str(tiaoguolist)
        else:
            nr='所有股票都成功更新'
        togmail.send('254370469@qq.com',bt,nr)
        print(bt)
        time.sleep(100)
bs.logout()