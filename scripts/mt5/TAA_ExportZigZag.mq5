//+------------------------------------------------------------------+
//| TAA_ExportZigZag.mq5                                             |
//| Exports the standard ZigZag(12,5,3) buffers with the bars' OHLC  |
//| to MQL5\Files\TAA_zigzag_<symbol>_<tf>.csv, one row per closed   |
//| bar (oldest first), so the bot's port can be compared with the   |
//| terminal (TAA-L813, docs/CHART_READ.md section 4.1).             |
//| Read-only: it creates an indicator handle and writes files; it   |
//| never trades.                                                    |
//+------------------------------------------------------------------+
#property script_show_inputs
#property strict

input string InpSymbols    = "XAUUSD,EURUSD,GBPUSD,USDJPY,AUDUSD"; // symbols, comma separated
input string InpTimeframes = "M15,H1,H4";                          // timeframes, comma separated
input int    InpBars       = 3000;                                 // closed bars per file
input int    InpDepth      = 12;
input int    InpDeviation  = 5;
input int    InpBackstep   = 3;

ENUM_TIMEFRAMES TfFromString(const string s)
  {
   if(s=="M1")  return(PERIOD_M1);
   if(s=="M5")  return(PERIOD_M5);
   if(s=="M15") return(PERIOD_M15);
   if(s=="M30") return(PERIOD_M30);
   if(s=="H1")  return(PERIOD_H1);
   if(s=="H4")  return(PERIOD_H4);
   if(s=="D1")  return(PERIOD_D1);
   return(PERIOD_CURRENT);
  }

bool ExportOne(const string symbol,const string tf_name)
  {
   ENUM_TIMEFRAMES tf=TfFromString(tf_name);
   if(tf==PERIOD_CURRENT)
     {
      PrintFormat("TAA: unknown timeframe %s",tf_name);
      return(false);
     }
   if(!SymbolSelect(symbol,true))
     {
      PrintFormat("TAA: symbol %s not available",symbol);
      return(false);
     }
   int handle=iCustom(symbol,tf,"Examples\\ZigZag",InpDepth,InpDeviation,InpBackstep);
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("TAA: iCustom failed for %s %s (error %d)",symbol,tf_name,GetLastError());
      return(false);
     }
   for(int tries=0; tries<200 && BarsCalculated(handle)<=0; tries++)
      Sleep(50);
   // start at position 1: the forming bar 0 is left out, as the bot reads closed bars only
   MqlRates rates[];
   double zz[],hmap[],lmap[];
   int n=CopyRates(symbol,tf,1,InpBars,rates);
   bool ok=n>0
           && CopyBuffer(handle,0,1,n,zz)==n
           && CopyBuffer(handle,1,1,n,hmap)==n
           && CopyBuffer(handle,2,1,n,lmap)==n;
   IndicatorRelease(handle);
   if(!ok)
     {
      PrintFormat("TAA: copy failed for %s %s (bars %d, error %d)",symbol,tf_name,n,GetLastError());
      return(false);
     }
   string name=StringFormat("TAA_zigzag_%s_%s.csv",symbol,tf_name);
   int f=FileOpen(name,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE)
     {
      PrintFormat("TAA: cannot write %s (error %d)",name,GetLastError());
      return(false);
     }
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   FileWrite(f,"time","open","high","low","close","zigzag","high_map","low_map","point","depth","deviation","backstep");
   for(int i=0; i<n; i++)
     {
      FileWrite(f,
                (long)rates[i].time,
                DoubleToString(rates[i].open,digits),
                DoubleToString(rates[i].high,digits),
                DoubleToString(rates[i].low,digits),
                DoubleToString(rates[i].close,digits),
                DoubleToString(zz[i],digits),
                DoubleToString(hmap[i],digits),
                DoubleToString(lmap[i],digits),
                DoubleToString(point,digits+1),
                InpDepth,InpDeviation,InpBackstep);
     }
   FileClose(f);
   PrintFormat("TAA: wrote %s (%d bars)",name,n);
   return(true);
  }

void OnStart()
  {
   string symbols[],tfs[];
   int ns=StringSplit(InpSymbols,',',symbols);
   int nt=StringSplit(InpTimeframes,',',tfs);
   int done=0;
   for(int s=0; s<ns; s++)
      for(int t=0; t<nt; t++)
        {
         StringTrimLeft(symbols[s]);
         StringTrimRight(symbols[s]);
         StringTrimLeft(tfs[t]);
         StringTrimRight(tfs[t]);
         if(ExportOne(symbols[s],tfs[t]))
            done++;
        }
   PrintFormat("TAA: %d of %d files written to %s\\MQL5\\Files",done,ns*nt,TerminalInfoString(TERMINAL_DATA_PATH));
  }
//+------------------------------------------------------------------+
