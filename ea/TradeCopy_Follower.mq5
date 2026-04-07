//+------------------------------------------------------------------+
//|  TradeCopy Cloud - FOLLOWER EA v2.1                              |
//|  Con cierre automatico cuando el master cierra                   |
//+------------------------------------------------------------------+
#property copyright "TradeCopy SaaS"
#property version   "2.10"
#property strict

#include <Trade\Trade.mqh>

input string   ServerURL      = "http://127.0.0.1:8000";
input string   EAToken        = "ea_XXXXX";
input int      PollIntervalMS = 1000;
input int      MaxSlippage    = 30;
input ulong    MagicNumber    = 20240101;
input bool     Debug          = false;

CTrade trade;
string PendingURL;
string AckURL;
string HbURL;

// Mapeo master ticket -> follower ticket
ulong masterTickets[];
ulong followerTickets[];
int   mappingCount = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   PendingURL = ServerURL + "/api/ea/follower/pending";
   AckURL     = ServerURL + "/api/ea/follower/ack";
   HbURL      = ServerURL + "/api/ea/follower/heartbeat";

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(MaxSlippage);

   EventSetMillisecondTimer(PollIntervalMS);
   Print("TradeCopy Follower EA v2.1 started.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
}

//+------------------------------------------------------------------+
void OnTimer()
{
   SendHeartbeat();
   CheckAndCopyTrades();
}

//+------------------------------------------------------------------+
void SendHeartbeat()
{
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);

   string params = StringFormat("?balance=%.2f&equity=%.2f&currency=%s",
                                balance, equity, currency);

   string headers = "X-EA-Token: " + EAToken;
   char   body[];
   char   resp[];
   string respHeaders;

   WebRequest("POST", HbURL + params, headers, 3000, body, resp, respHeaders);
}

//+------------------------------------------------------------------+
void CheckAndCopyTrades()
{
   string headers = "X-EA-Token: " + EAToken;
   char   bodyBytes[];
   char   respBytes[];
   string respHeaders;

   int res = WebRequest("GET", PendingURL, headers, 3000,
                        bodyBytes, respBytes, respHeaders);

   if(res != 200)
   {
      if(Debug) Print("Poll error: HTTP ", res);
      return;
   }

   string json = CharArrayToString(respBytes);
   if(Debug) Print("Pending response: ", json);

   // --- CIERRE AUTOMATICO ---
   // Buscar trades que tenemos abiertos pero ya no estan en el master
   CloseOrphanTrades(json);

   // --- APERTURA ---
   // Abrir trades nuevos del master
   ParseAndCopyPositions(json);
}

//+------------------------------------------------------------------+
void CloseOrphanTrades(string json)
{
   // Para cada trade que abrimos (mappingCount), verificar si el
   // master ticket sigue en el JSON de posiciones pendientes.
   // Si no esta, el master lo cerro y debemos cerrar el nuestro.

   for(int i = 0; i < mappingCount; i++)
   {
      ulong mTicket = masterTickets[i];
      ulong fTicket = followerTickets[i];

      if(mTicket == 0 || fTicket == 0) continue;

      // Buscar si el master ticket sigue en el JSON
      string ticketStr = "\"ticket\":" + IntegerToString((long)mTicket);
      bool masterStillOpen = (StringFind(json, ticketStr) >= 0);

      if(!masterStillOpen)
      {
         // El master cerro ese trade — cerramos el nuestro
         if(PositionSelectByTicket(fTicket))
         {
            string symbol = PositionGetString(POSITION_SYMBOL);
            bool closed = trade.PositionClose(fTicket, MaxSlippage);

            if(closed)
            {
               Print("Auto-closed follower ticket #", fTicket,
                     " (master ticket #", mTicket, " was closed)");
               // Limpiar del mapeo
               masterTickets[i]  = 0;
               followerTickets[i] = 0;
            }
            else
            {
               Print("Failed to close follower ticket #", fTicket,
                     " Error: ", trade.ResultRetcode());
            }
         }
         else
         {
            // Ya no existe localmente, limpiar igualmente
            masterTickets[i]  = 0;
            followerTickets[i] = 0;
         }
      }
   }
}

//+------------------------------------------------------------------+
void ParseAndCopyPositions(string json)
{
   int posStart = StringFind(json, "\"positions\":[");
   if(posStart < 0) return;
   posStart += 13;

   int posEnd = StringFind(json, "]", posStart);
   if(posEnd < 0) return;

   string posArray = StringSubstr(json, posStart, posEnd - posStart);
   if(StringLen(posArray) < 5) return;

   double lotMultiplier = ParseDouble(json, "lot_multiplier", 1.0);
   double fixedLot      = ParseDouble(json, "fixed_lot", 0);
   double maxLot        = ParseDouble(json, "max_lot", 0);
   bool   copySL        = ParseBool(json, "copy_sl", true);
   bool   copyTP        = ParseBool(json, "copy_tp", true);
   bool   reverse       = ParseBool(json, "reverse", false);

   int searchPos = 0;
   while(true)
   {
      int objStart = StringFind(posArray, "{", searchPos);
      if(objStart < 0) break;

      int objEnd = StringFind(posArray, "}", objStart);
      if(objEnd < 0) break;

      string posObj = StringSubstr(posArray, objStart, objEnd - objStart + 1);

      ulong masterTicket = (ulong)ParseLong(posObj, "ticket", 0);
      if(masterTicket > 0 && !IsAlreadyCopied(masterTicket))
      {
         string symbol = ParseString(posObj, "mapped_symbol", "");
         if(symbol == "") symbol = ParseString(posObj, "symbol", "");
         string action = ParseString(posObj, "action", "buy");
         double lots   = ParseDouble(posObj, "lots", 0.01);
         double sl     = ParseDouble(posObj, "sl", 0);
         double tp     = ParseDouble(posObj, "tp", 0);

         double finalLots;
         if(fixedLot > 0)
            finalLots = fixedLot;
         else
            finalLots = lots * lotMultiplier;

         if(maxLot > 0 && finalLots > maxLot)
            finalLots = maxLot;

         finalLots = MathMax(0.01, NormalizeDouble(finalLots, 2));

         if(reverse)
            action = (action == "buy") ? "sell" : "buy";

         if(!copySL) sl = 0;
         if(!copyTP) tp = 0;

         CopyTrade(masterTicket, symbol, action, finalLots, sl, tp);
      }

      searchPos = objEnd + 1;
      if(searchPos >= StringLen(posArray)) break;
   }
}

//+------------------------------------------------------------------+
void CopyTrade(ulong masterTicket, string symbol, string action,
               double lots, double sl, double tp)
{
   bool  success = false;
   ulong followerTicket = 0;

   if(action == "buy")
   {
      double price = SymbolInfoDouble(symbol, SYMBOL_ASK);
      success = trade.Buy(lots, symbol, price, sl, tp, "TradeCopy");
   }
   else
   {
      double price = SymbolInfoDouble(symbol, SYMBOL_BID);
      success = trade.Sell(lots, symbol, price, sl, tp, "TradeCopy");
   }

   if(success)
   {
      followerTicket = trade.ResultOrder();
      Print("Copied: ", symbol, " ", action, " ", lots,
            " lots. Master #", masterTicket, " -> Follower #", followerTicket);

      // Guardar el mapeo master -> follower
      ArrayResize(masterTickets,  mappingCount + 1);
      ArrayResize(followerTickets, mappingCount + 1);
      masterTickets[mappingCount]  = masterTicket;
      followerTickets[mappingCount] = followerTicket;
      mappingCount++;

      SendAck(masterTicket, followerTicket, symbol, lots, "copied", "");
   }
   else
   {
      Print("FAILED to copy: ", symbol, " ", action,
            " Error: ", trade.ResultRetcode());
      SendAck(masterTicket, 0, symbol, lots, "failed",
              IntegerToString(trade.ResultRetcode()));
   }
}

//+------------------------------------------------------------------+
void SendAck(ulong masterTicket, ulong followerTicket, string symbol,
             double lots, string status, string error)
{
   string body = StringFormat(
      "{\"master_ticket\":%llu,\"follower_ticket\":%llu,"
      "\"symbol\":\"%s\",\"lots\":%.2f,\"status\":\"%s\",\"error\":\"%s\"}",
      masterTicket, followerTicket, symbol, lots, status, error
   );

   string headers = "Content-Type: application/json\r\nX-EA-Token: " + EAToken;
   char bodyBytes[];
   char respBytes[];
   string respHeaders;
   StringToCharArray(body, bodyBytes, 0, StringLen(body));
   WebRequest("POST", AckURL, headers, 3000, bodyBytes, respBytes, respHeaders);
}

//+------------------------------------------------------------------+
bool IsAlreadyCopied(ulong ticket)
{
   for(int i = 0; i < mappingCount; i++)
      if(masterTickets[i] == ticket) return true;
   return false;
}

//+------------------------------------------------------------------+
double ParseDouble(string json, string key, double def)
{
   string pattern = "\"" + key + "\":";
   int pos = StringFind(json, pattern);
   if(pos < 0) return def;
   pos += StringLen(pattern);
   return StringToDouble(StringSubstr(json, pos, 20));
}

long ParseLong(string json, string key, long def)
{
   string pattern = "\"" + key + "\":";
   int pos = StringFind(json, pattern);
   if(pos < 0) return def;
   pos += StringLen(pattern);
   return StringToInteger(StringSubstr(json, pos, 20));
}

bool ParseBool(string json, string key, bool def)
{
   string pattern = "\"" + key + "\":";
   int pos = StringFind(json, pattern);
   if(pos < 0) return def;
   return StringFind(StringSubstr(json, pos + StringLen(pattern), 5), "true") >= 0;
}

string ParseString(string json, string key, string def)
{
   string pattern = "\"" + key + "\":\"";
   int pos = StringFind(json, pattern);
   if(pos < 0) return def;
   pos += StringLen(pattern);
   int end = StringFind(json, "\"", pos);
   if(end < 0) return def;
   return StringSubstr(json, pos, end - pos);
}
//+------------------------------------------------------------------+