# EmpowerBands Activation Code Operations

## Phone workflow

1. Sign in at `https://www.empowerbands.org/admin`.
2. Open **Activation Codes**.
3. Tap **Generate One Safety ID**, or select 10, 25, 50, 100, or 200 and tap **Generate Batch**.
4. Use **Print card** for one unit or **Print newly generated batch** for the whole batch.
5. Assign each available unit to a store before it leaves EmpowerBands inventory.

The generator writes directly to PostgreSQL. Do not create or upload an
`activation_codes.csv` file.

## Store preparation workflow

1. Generate the required batch.
2. Print the batch and match each card to its physical Safety ID.
3. Search or filter the inventory, enter the store or organization name and an
   optional shipment/order note, then save the assignment.
4. Package each printed card with its matching unit. Keep codes covered from
   public view until purchase.
5. Download the filtered CSV only when an internal inventory copy is required.
   Store the download in an access-controlled location; never commit it to Git.
6. If an unused card is lost or exposed, search its Safety ID, type the exact ID
   in the confirmation field, and choose **Revoke & replace**. Destroy the old
   card and print the replacement.
7. If an ID is already claimed, do not reassign or rotate it in this manager.
   Verify ownership through a separate support recovery process before any
   database administrator changes customer data.

## Publicly exposed legacy inventory

The removed public CSV marked these Safety IDs as unclaimed: **EB004, EB013,
and EB018**. Their activation codes remain exposed in Git history even though
the file is no longer tracked.

After this feature is approved and deployed:

1. Sign in to the Activation Code Manager.
2. Search each ID above individually.
3. If it is still **Available**, use **Revoke & replace**, then print a new card.
4. If it is **Claimed**, do not rotate it. Record that it was already claimed and
   use the protected customer-verification recovery process if fraud is suspected.
5. Confirm the old unclaimed code no longer activates and the replacement does.

This procedure never prints existing customer data and never changes a claimed
profile automatically.
