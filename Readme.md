
# Pyzcto

Pyzcto is a front-end  for the official zcash client. It also allows to set up an onion service to be used by the [Zcash Pannel](https://github.com/miguelmarco/ZcashPannel) android app.

## Dependencies

In order to use this program, you need to have the following:

- The zcashd daemon running (**warning**: make sure that it is setup with a username and a nontrivial password, otherwise you risk somebody else taking control of your funds).
- Python (should work on either version 2 or 3, but non-ascii characters in your address aliases might cause crashes under python2). With the following packages (check if you have to install them with your distro's package manager or via pip):
  - PyQt5
  - requests
  - simplejson
  - qrcode
- A tor client installed (just install it with your distro's package manager)

## Running

Just open a terminal, cd to the pyzcto directory, and run `python pyzcto.py`.

It should open a window, and show in the bottom bar the message "connected to 127.0.0.1:8232" If it doesn't, go to the "Zcash" pannel and set up the configuration properly.

### The "Addresses" tab

This tab shows your addresses and a list of external addresses you want to keep track of. You can edit the "Alias" column to help you remember each address.

If you right-click over a transparent address, you have the option of showing the corresponding public key. It will be useful if you want to deal with multisig addresses (see later).

### The "Available" tab

Here you can see the available utxos (think of them as coins) of your transparent addresses, and the received transactions to your shielded addresses. The color deppends on the confirmations they have: they start at red when there are very few confirmations, and turn to green as they receive more confirmations. You can also see your total balance.

If you leave the cursor over a received shielded transaction for a second, you will see the encrypted memo field of the transaction (if there is any).

### The "Historial" tab

Here you ca see your history of sent and received transactions.

### The "Send" tab

#### "Send to single address"

Here is where you send funds from one of you addresses to other address. Just select the address you want to send from, the address you want to send to, amount and fee, and click the Send button.

In the "Ongoing operations" area you will see the details of the transactions that are being processed (transparent transactions would be done immediately, but shielded transactions might get a couple of minutes). Once they are finished, you will see the result of them in the "Finished operations" (including error messages if there are any).

#### "Send to multiple address"

As before, but here you can add several destinations for your funds. There should be a destination per line .You can either paste an encoded requests, or write the address, amount and memo field (if any) separated by commas.

Example:

tmQPikvLZxaV76XR7rDuKLuKNfZ2Gw2HjwZ,2.56 would send 2.56 zcash to the address tmQPikvLZxaV76XR7rDuKLuKNfZ2Gw2HjwZ and so on.

### The "Receive" tab

Just select one of you addresses, an amount and a comment (optional), and a QR code with the request will be shown. You will also see the encoded request in the bottom (which you can copy and send to other person to request that payment).

Here you can also create new transparent or shielded addresses.

### The "Multisig" tab

Here we deal with multisig addresses. There are two subtabs, one for creating new multisg addresses, and the other to spend funds from multisig addresses.

**Warning**: The main reason for using zcash is the privacy it provides (so I recommend to use always shielded addresses), but multisig addresses are transparent, and can only be spent to transparent address. I recommend to use each transparent address only once, and follow this scheme when dealing with multisig addresses:

Shielded address --> One-time multisig address (made of one time transparent addresses)--> One-time transparent address -> Shielded address

That way, the only information that will be published is that somebody made a payment of a known amount to somebody through an m of n multisig. Consider carefully if that information leak is acceptable for your needs or not.

#### Create/Import

If you want to create an n of m multisig address, paste the public keys of m transparent addresses (one per line) in the first text edit area (typically, one will be yours and the rest will be addresses of the other signers), and select the number of required signatures. In the case of addresses that are already in your wallet, you can paste directly the address (but will need to send the public address to your cosigners anyways), but otherwise you will need the public key itself (they can be obtained with a right click in the "Addresses" tab). If they are correct, you will see that the "Address (to send funds to)" and "Redeem script" will be filled, and the "Import to wallet" button would be enabled. You can push the button to include the multisig address in your wallet, and copy the redeem script and send it to the other signers for imorting it. You can also send the list of public addresses (in the same order as they entered), and the number of minimal signatures so they can repeat the creation process.

The button "Create New Public Key" will create a new transparent address in your wallet and automatically paste the corresponding public key in the list. This is recommended, since reusing keys might result in reduced privacy.

If you received a list of public addresses from somebody else, just paste them in the "Addresses/Keys" field, choose the number of minimal transactions, and the rest of the fields should be filled automatically. Check that it is correct (in particular, at least one of the addresses should be yours, and the rest should correspond to the other signers, the address and redeem script should match the ones you got from your cosigner) and import the multisig address to your wallet as before. If you received a redeem script, paste it in the corresponding area and the keys and minimal sugnatures will be filled automatically.

Note that, when you push the "Import" button, a dialog will appear asking if you want to rescan the whole blockchain. If you decide to rescan it, it will take some time (expect several minutes at least), during which the program will be irresponsive. Rescanning the blockchain is necessary for the wallet to be aware of the funds sent to this address before this moment. If you are sure that the multisig address has not yet been funded (for example, because you just created it), or rely on other signer to create the payment orders that you will just sign, it is probably better to choose not to rescan.

Now the address can be funded by sending funds to it just like any other address.

#### Sign/send

Here you can spend funds from a multisig address (if you have enough signatures that authorize that payment). The workflow is as follows: one of the authorized signers creates a payment order, signs it and sends it to another authorized signer. This second signer checks that the payment order is valid, and signs it, then sends it to another signer and so on. When there are enough signatures, the payment order can be broadcasted to the network and the funds will be sent from the multisig address to the addresses specified in the order.

The creator of the payment order should select the multisig address to spend from, and add a list of addresses to spend to, together with the amount to send to each one. He can either enter them directly with the format address,amount (one in each line) or can use the "Add" button, that will add a line with the selected address and amount. If the addresses and amounts are valid, a payment order will be generated. By clicking the "sign" button, the order will be signed with the keys of this user (the text of the order should change). Now this payment order can be copied and sent to the next signer.

If you receive a payment order, paste it in the "payment order" field and the rest of the fields should be filled automatically, showing you the details of the payment order. If you agree with it, press the "sign" button to add your signature to the order. If the order has enough signatures, you can click the "broadcast" button to send the order to the zcash network, executing hence the payment. If more signatures are needed, copy the order and send it to the next signer.

### The "Tor" tab

Here you can start a tor .onion service that would allow you to access your wallet from your android phone with the [Zcash Pannel](https://github.com/miguelmarco/ZcashPannel) app. If you can connect directly to the tor network, just click on the "connect" button. A qr code should appear and some output appear should appear in the bottom text area. If you see the message "Bootstrapped 100%: Done" it means that you are connected to the tor network. You can setup your ZcashPannel app scanning the QR code.

Notice that the .onion service can take some properly setup. If you cannot connect from your android app immediately, just wait a minute or so and try again.

If you need a proxy to connect to the tor network, just check the corresponding checkbox and configure it. Even though the interface shows some options for using bridges, the program does not use them at the moment.

### The "Zcash" tab

Here you can configure how to connect to your zcashd daemon. It should be autimatically configured by default, but if it fails to connect, you can set here the parameters.



## Donate

I accept donations in the address zcayBTtUDZRU6rLsXApP3DbLEsxJa9M7WeigUEv1PQd6sodxHAeRgS3vSN4kh9e81r6Y1cngKdhQdTbsRhUnSJqHHeQGpkJ
