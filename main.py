from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import db_helper
import helper2
app = FastAPI()
inprogress_orders={}
@app.post("/")
async def handle_request(request: Request):
    try:
        # Retrieve the JSON payload from the Dialogflow request
        payload = await request.json()

        # Safely extract necessary fields
        intent = payload.get("queryResult", {}).get("intent", {}).get("displayName", "")
        parameters = payload.get("queryResult", {}).get("parameters", {})
        output_contexts = payload.get("queryResult", {}).get("outputContexts", [])
        session_id=helper2.extract_session_id(output_contexts[0]['name'])

        # Check for the specific intent
        intent_handler_dict={
            "order.add-context:ongoing-order":add_order,
            "order.complete-context:ongoing-order":complete_order,
            "order.remove-context:ongoing-order":remove_from_order,
            "track.order:ongoing-tracking":track_order
        }
        print(f"Received intent: {intent}")
        return intent_handler_dict[intent](parameters,session_id)
        # If intent does not match, return a default response

    except Exception as e:
        # Return an error message for debugging
        return JSONResponse(content={"fulfillmentText": f"Error: {str(e)}"})
def add_order(parameters: dict,session_id: str):
    food_items=parameters["food-item"]
    quantities=parameters["number"]

    if len(food_items)!=len(quantities):
       fulfillment_text = "Sorry but the quantity and the food items specified aren't matching."
    else:
        new_food_dict=dict(zip(food_items,quantities))
        if session_id in inprogress_orders:
            current_food_dict=inprogress_orders[session_id]
            current_food_dict.update(new_food_dict)
            inprogress_orders[session_id]=current_food_dict
        else:
            inprogress_orders[session_id]=new_food_dict
        order_str=helper2.get_str_from_food_dict(inprogress_orders[session_id])
        fulfillment_text = f"So far you have: {order_str}. Do you need anything else? "
    return JSONResponse(content={"fulfillmentText": fulfillment_text})
def track_order(parameters: dict,session_id: str):
    order_id = parameters.get("orderId")

    # Simulate database retrieval using db_helper
    order_status = db_helper.get_order_status(order_id)

    if order_status:
        fulfillment_text = f"The order status is {order_status} for the order id {order_id}."
    else:
        fulfillment_text = f"No order with the order id {order_id} was found."

    return JSONResponse(content={"fulfillmentText": fulfillment_text})
def complete_order(parameters: dict,session_id: str):
    if session_id not in inprogress_orders:
        fulfillment_text = "I'm having trouble finding you order. Sorry! can you place a new order"
    else:
        order=inprogress_orders[session_id]
        order_id=save_to_db(order)

        if order_id ==-1:
            fulfillment_text = f"Sorry, I couldn't process your order due to a backend error. " \
                                "Please place a new order."
        else:
            order_total=db_helper.get_total_order_price(order_id)
            fulfillment_text=f"Awesome we have placed your order. " \
                             f"Here is your order_id #{order_id}. " \
                             f"Your order total is {order_total} which you can pay at the end of the delivery. "
    del inprogress_orders[session_id]
    return JSONResponse(content={"fulfillmentText": fulfillment_text})

def save_to_db(order):
    next_order_id=db_helper.get_next_order_id()
    for food_item,quantity in order.items():
        rcode=db_helper.insert_order_item(
            food_item,
            quantity,
            next_order_id
        )
        if rcode==-1:
            print(f"Failed to insert {food_item}. Rolling back transaction.")
            return -1
    db_helper.insert_order_tracking(next_order_id,"in progress")
    return next_order_id

def remove_from_order(parameters:dict,session_id: str):
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText":"I am having trouble processing your request. Could you provide a better request."
        })
    current_order=inprogress_orders[session_id]
    food_items=parameters["food-item"]
    removed_items=[]
    no_such_items=[]
    for item in food_items:
        if item not in current_order:
            no_such_items.append(item)
            pass
        else:
            removed_items.append(item)
            del current_order[item]
    if len(removed_items)>0:
        fulfillment_text=f"Removed {",".join(removed_items)} from your order."
    if len(no_such_items)>0:
        fulfillment_text=f"Your current order does not have {",".join(no_such_items)}."
    if len(current_order.keys())==0:
        fulfillment_text +=" Your order is empty!!"
    else:
        order_str=helper2.get_str_from_food_dict(current_order)
        fulfillment_text +=f" Here is what is left in your order: {order_str}."
    return JSONResponse(content={"fulfillmentText": fulfillment_text})
