@app.route('/ussd', methods=['POST', 'GET'])
def ussd():
    phoneNumber = request.values.get("phoneNumber", "").strip()
    text = request.values.get("text", "")
    sessionId = request.values.get("sessionId", "")
    
    print(f"Phone: {phoneNumber}, Text: '{text}', Session: {sessionId}")
    
    # Parse the user's menu path
    user_input = text.split('*') if text else []
    level = len(user_input)
    
    # Get the main menu option (first number user pressed)
    main_option = user_input[0] if user_input else ""
    
    # ========== MAIN MENU (First visit or no input) ==========
    if text == "":
        response = "CON Welcome to AgriKwacha. Your farming payment platform. "
        response += "1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
        return send_response(response)
    
    # ========== OPTION 1: Register Delivery ==========
    if main_option == "1":
        # Level 1: Show product menu
        if level == 1:
            response = "CON Select product. 1. Maize. 2. Soya Beans. 3. Cattle. 4. Pigs. 5. Sunflower. 6. Tobacco. 0. Back"
            return send_response(response)
        
        # Level 2: Product selected, show depot menu
        elif level == 2:
            product_map = {
                "1": "Maize", "2": "Soya Beans", "3": "Cattle",
                "4": "Pigs", "5": "Sunflower", "6": "Tobacco"
            }
            product = product_map.get(user_input[1], "Unknown")
            
            # Store selected product in session
            sessions[sessionId] = {"product": product}
            
            response = "CON Select depot. 1. Zambeef Lusaka. 2. AFGRI Mkushi. 3. Mwila Mills Ndola. 0. Back"
            return send_response(response)
        
        # Level 3: Depot selected, show confirmation
        elif level == 3:
            depot_map = {
                "1": "Zambeef Lusaka",
                "2": "AFGRI Mkushi", 
                "3": "Mwila Mills Ndola"
            }
            depot = depot_map.get(user_input[2], "Unknown")
            product = sessions.get(sessionId, {}).get("product", "Unknown")
            
            response = f"CON Confirm delivery. Product: {product}. Depot: {depot}. 1. Confirm. 2. Cancel"
            return send_response(response)
        
        # Level 4: Confirmation
        elif level == 4:
            if user_input[3] == "1":
                import random
                delivery_ref = f"DLV-{random.randint(10000, 99999)}"
                response = f"END Delivery registered. Ref: {delivery_ref}. Show this at the depot."
            else:
                response = "END Delivery cancelled."
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # ========== OPTION 2: My Payments ==========
    elif main_option == "2":
        farmer = get_farmer_by_phone(phoneNumber)
        if farmer:
            name = farmer['fields'].get('Full Name', 'Farmer')
            response = f"END {name}. No payments yet. Register a delivery to get started."
        else:
            response = "END You are not registered. Please contact support."
        return send_response(response)
    
    # ========== OPTION 3: Confirm Delivery ==========
    elif main_option == "3":
        if level == 1:
            response = "CON Enter your delivery reference number. Example DLV-12345. 0. Back"
            return send_response(response)
        elif level == 2:
            if user_input[1] == "0":
                response = "CON Welcome to AgriKwacha. 1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
            else:
                response = f"END Delivery {user_input[1]} confirmed. Your payment is being processed."
            return send_response(response)
    
    # ========== OPTION 4: Help ==========
    elif main_option == "4":
        response = "END For help, call AgriKwacha support at 0977 123 456."
        return send_response(response)
    
    # ========== OPTION 0: Exit ==========
    elif main_option == "0":
        response = "END Thank you for using AgriKwacha. Goodbye."
        return send_response(response)
    
    # ========== Default ==========
    else:
        response = "END Invalid option. Please try again."
        return send_response(response)