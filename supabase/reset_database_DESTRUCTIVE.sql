-- ############################################################################
-- #                                                                          #
-- #   THIS FILE DELETES EVERYTHING.                                          #
-- #                                                                          #
-- #   Running it drops the users, documents and document_chunks tables and    #
-- #   every row in them: all accounts, all uploaded files, all embeddings.    #
-- #   There is no undo. Recovery means a Supabase backup restore, or          #
-- #   re-registering accounts and re-uploading every document by hand.        #
-- #                                                                          #
-- #   You almost certainly want one of these instead:                        #
-- #                                                                          #
-- #     schema.sql              - create anything missing, harms nothing      #
-- #     migrations/*.sql        - replace functions only, harms nothing       #
-- #                                                                          #
-- #   Use this file only to deliberately wipe a scratch project. After        #
-- #   running it, run schema.sql to rebuild the empty tables.                 #
-- #                                                                          #
-- ############################################################################

drop table if exists document_chunks cascade;
drop table if exists documents cascade;
drop table if exists users cascade;
