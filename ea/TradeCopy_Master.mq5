//+------------------------------------------------------------------+
//|  TradeCopy Cloud - MASTER EA                                      |
//|  Sends open positions to the cloud every second                   |
//+------------------------------------------------------------------+
#property copyright "TradeCopy SaaS"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>

input string   ServerURL    = "http://localhost:8000";
input string   EAToken      = "ea_XXXXX";
input int      HeartbeatMS  = 1000;
input bool     SendOnEvent  = true;
input bool     Debug        = false;

string HeartbeatURL;
string AuthHeader;

//+------------------------------------------------------------------+
int OnInit()
{
   HeartbeatURL = ServerURL + "/api/ea/master/heartbeat";
   AuthHeader   = "X-EA-Token: " + EAToken;
   EventSetMillisecondTimer(HeartbeatMS);
   Print("TradeCopy Master EA started. Server: ", ServerURL);
   SendHeartbeat();
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("TradeCopy Master EA stopped.");
}

//+------------------------------------------------------------------+
void OnTimer()
{
   SendHeartbeat();
}

//+------------------------------------------------------------------+
void OnTrade()
{
   if(SendOnEvent)
   {
      Sleep(200);
      SendHeartbeat();
   }
}

//+------------------------------------------------------------------+
void SendHeartbeat()
{
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);

   string positionsJson = "[";
   int total = PositionsTotal();

   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;

      string symbol  = PositionGetString(POSITION_SYMBOL);
      int    type    = (int)PositionGetInteger(POSITION_TYPE);
      double lots    = PositionGetDouble(POSITION_VOLUME);
      double oprice  = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl      = PositionGetDouble(POSITION_SL);
      double tp      = PositionGetDouble(POSITION_TP);
      double profit  = PositionGetDouble(POSITION_PROFIT);
      datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
      string action  = (type == POSITION_TYPE_BUY) ? "buy" : "sell";

      if(i > 0) positionsJson += ",";
      positionsJson += StringFormat(
         "{\"ticket\":%llu,\"symbol\":\"%s\",\"action\":\"%s\","
         "\"lots\":%.2f,\"open_price\":%.5f,\"sl\":%.5f,\"tp\":%.5f,"
         "\"profit\":%.2f,\"opened_at\":\"%s\"}",
         ticket, symbol, action,
         lots, oprice, sl, tp, profit,
         TimeToString(openTime, TIME_DATE|TIME_SECONDS)
      );
   }
   positionsJson += "]";

   string body = StringFormat(
      "{\"balance\":%.2f,\"equity\":%.2f,\"currency\":\"%s\",\"positions\":%s}",
      balance, equity, currency, positionsJson
   );

   string headers = "Content-Type: application/json\r\n" + AuthHeader;

   char   bodyBytes[];
   char   responseBytes[];
   string responseHeaders;

   StringToCharArray(body, bodyBytes, 0, StringLen(body));

   int res = WebRequest(
      "POST", HeartbeatURL, headers, 3000,
      bodyBytes, responseBytes, responseHeaders
   );

   if(res == 200)
   {
      if(Debug) Print("Heartbeat OK. Positions: ", total);
   }
   else if(res < 0)
   {
      Print("WebRequest FAILED. Error: ", GetLastError(),
            " — Add '", ServerURL, "' to MT5 allowed URLs (Tools > Options > Expert Advisors)");
   }
   else
   {
      if(Debug) Print("Heartbeat HTTP ", res, ": ", CharArrayToString(responseBytes));
   }
}
//+------------------------------------------------------------------+