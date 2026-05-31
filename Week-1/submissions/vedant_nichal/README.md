# Rail Ticket Agent

## Description

here the agent works on the start station and end station that user gives to give the available routes with ticket availability and prices
right now it works only for one sided travel i.e. it works for pune to hyderabad and not from hyderabad to pune
will add this later on
also the price of the ticket is decided by the start and end station as the price of travel between 2 stations might be different

## Tools

1. search_stations:
searches the routes which can be used

2. check_ticket_availability
checks tickets available for the next 3 days

3. ticket_prices
gives the price for ticket on all routes that can be taken

## Current Limitations

- Supports one-direction travel only
- Cannot decide if there are tickets for in between travek

## Demo input

"i need to go to kurudwadi by train from pune, find me a train route and check ticket availabity on next 2 days and give the number of tickets available on each days with the ticket price",
"i need to go to solapur from hadapsar, find me a train route and price with ticket availability",
"give me ticket prices if i want to go from daund to latur"

## Demo output (final outputs)

------------------------------------------------------------

FINAL ANSWER:
Train routes from Pune to Kurudwadi:
- **pune solapur**: 25 tickets on day 1, 56 tickets on day 2
- **pune hyderabad**: 0 tickets on day 1, 12 tickets on day 2

Ticket prices:
- **pune solapur**: ₹155
- **pune hyderabad**: ₹140

Note: "pune hyderabad" has no tickets available on day 1.
------------------------------------------------------------

FINAL ANSWER:
The only train route from hadapsar to solapur is **pune solapur**.  
- **Ticket availability**: 25 tickets on day 1, 56 tickets on day 2, 97 tickets on day 3.  
- **Ticket price**: ₹110 for this route (available on all 3 days with no unavailability).
------------------------------------------------------------

FINAL ANSWER:
The train route that includes both Daund and Latur is **pune hyderabad**.  
The ticket price for this route is **₹270** for all three days (no tickets unavailable).
------------------------------------------------------------
