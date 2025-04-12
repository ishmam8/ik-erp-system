def check_expiry():
    '''Checks for expired transactions from PendingTransaction table. 
       Marks them as expired
       Move back the vgt_amount to the sender's balance
       Notifies the sender via email
       Notifies the target user via email
       Notifies the admin via email
       Deletes the expired transaction
    '''

    pass